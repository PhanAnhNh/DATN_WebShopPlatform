import json

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, logger
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.payment_model import PaymentCreate, MomoPaymentRequest, VNPayPaymentRequest
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from typing import Optional

from app.services.sepay_service import SePayService
from app.services.shop_settings_service import ShopSettingsService

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.post("/create")
async def create_payment(
    payment_data: PaymentCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Tạo yêu cầu thanh toán"""
    service = PaymentService(db)
    
    result, error = await service.create_payment(
        str(current_user.id),
        payment_data.dict()
    )
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return result

@router.post("/momo/ipn")
async def momo_ipn(
    request: Request,
    db = Depends(get_database)
):
    """IPN từ MoMo (gọi tự động)"""
    data = await request.json()
    service = PaymentService(db)
    
    # Xử lý thanh toán
    result = await service.process_momo_ipn(data)
    
    # ========== TẠO THÔNG BÁO NẾU THANH TOÁN THÀNH CÔNG ==========
    if data.get('resultCode') == 0:
        notification_service = NotificationService(db)
        
        # Lấy thông tin order
        order = await db["orders"].find_one({"_id": ObjectId(data['orderId'])})
        if order:
            order_code = data['orderId'][-8:].upper()
            await notification_service.create_notification(
                user_id=str(order["user_id"]),
                type="payment",
                title="Thanh toán thành công",
                message=f"Đơn hàng #{order_code} đã thanh toán thành công",
                reference_id=data['orderId']
            )
    # ========== KẾT THÚC TẠO THÔNG BÁO ==========
    
    return result

@router.get("/vnpay/return")
async def vnpay_return(
    request: Request,
    db = Depends(get_database)
):
    """Return từ VNPay"""
    params = dict(request.query_params)
    service = PaymentService(db)
    return await service.process_vnpay_return(params)

@router.get("/{payment_id}")
async def get_payment(
    payment_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy thông tin thanh toán"""
    payment = await db["payments"].find_one({"_id": ObjectId(payment_id)})
    
    if not payment:
        raise HTTPException(status_code=404, detail="Không tìm thấy thanh toán")
    
    payment["_id"] = str(payment["_id"])
    payment["order_id"] = str(payment["order_id"])
    payment["user_id"] = str(payment["user_id"])
    
    return payment

@router.get("/instructions/{order_id}")
async def get_payment_instructions(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy thông tin hướng dẫn thanh toán cho đơn hàng"""
    order = await db["orders"].find_one({
        "_id": ObjectId(order_id),
        "user_id": ObjectId(current_user.id)
    })
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Lấy thông tin ngân hàng từ settings
    bank_settings = await db["settings"].find_one({"key": "bank_info"})
    
    return {
        "order_id": order_id,
        "amount": order["total_amount"],
        "bank_info": bank_settings.get("value", {}) if bank_settings else {},
        "qr_code_url": f"/static/qr/{order_id}.png"  # Tạo QR code động nếu có
    }

@router.post("/bank-transfer/webhook")
async def bank_transfer_webhook(
    request: Request,
    db = Depends(get_database)
):
    """
    Webhook nhận dữ liệu từ SEPAY khi có giao dịch mới.
    SEPAY gửi JSON: { "transaction_id": "...", "amount": 65000, "description": "#ABC123", "account_number": "10688120730", ... }
    """
    data = await request.json()
    service = PaymentService(db)
    result = await service.process_bank_transfer_webhook(data)
    return result

@router.get("/generate-qr/{order_id}")
async def generate_qr_for_order(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Tạo QR code động cho đơn hàng (bank transfer)"""
    # Kiểm tra order
    order = await db["orders"].find_one({
        "_id": ObjectId(order_id),
        "user_id": ObjectId(current_user.id)
    })
    if not order:
        raise HTTPException(404, "Order not found")
    
    if order.get("payment_status") == "paid":
        raise HTTPException(400, "Order already paid")
    
    # Tạo order_code
    order_code = str(order["_id"])[-8:].upper()
    
    # Tạo QR code
    sepay_service = SePayService(db)
    qr_url = await sepay_service.generate_qr_code(order_id, order_code, order["total_amount"])
    
    if not qr_url:
        raise HTTPException(500, "Failed to generate QR code")
    
    return {"qr_code_url": qr_url}


@router.post("/sepay/webhook")
async def sepay_webhook(
    request: Request,
    db = Depends(get_database)
):
    """
    Webhook nhận dữ liệu từ SePay khi có giao dịch mới.
    """
    try:
        # Log request headers để debug
        logger.info("=" * 50)
        logger.info("🔔 SePay webhook called!")
        logger.info(f"📋 Headers: {dict(request.headers)}")
        
        # Lấy raw data
        data = await request.json()
        
        # Log chi tiết data nhận được
        logger.info(f"📦 Webhook data received: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # Xử lý webhook
        sepay_service = SePayService(db)
        result = await sepay_service.process_webhook(data)
        
        logger.info(f"✅ Webhook processed. Result: {result}")
        logger.info("=" * 50)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ SePay webhook error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    
@router.post("/sepay/test-webhook")
async def test_sepay_webhook(
    request: Request,
    db = Depends(get_database)
):
    """Test endpoint để simulate webhook từ SePay"""
    try:
        data = await request.json()
        logger.info("🧪 TEST webhook received")
        logger.info(f"📦 Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        sepay_service = SePayService(db)
        result = await sepay_service.process_webhook(data)
        
        return {"status": "test_success", "result": result}
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        return {"status": "error", "message": str(e)}