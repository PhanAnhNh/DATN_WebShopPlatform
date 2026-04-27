from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.payment_model import PaymentCreate, MomoPaymentRequest, VNPayPaymentRequest
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from typing import Optional

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
    order = await db["orders"].find_one({
        "_id": ObjectId(order_id),
        "user_id": ObjectId(current_user.id)
    })
    if not order:
        raise HTTPException(404, "Order not found")
    
    if order.get("payment_method") not in ["bank", "bank_transfer"]:
        raise HTTPException(400, "Only for bank transfer orders")
    
    if order.get("payment_status") == "paid":
        raise HTTPException(400, "Order already paid")
    
    # Lấy thông tin tài khoản ngân hàng từ shop settings
    # items là list, mỗi item có shop_id
    items = order.get("items", [])
    if not items:
        raise HTTPException(400, "Order has no items")
    shop_id = items[0].get("shop_id")
    if not shop_id:
        raise HTTPException(400, "Shop not found")
    
    settings_service = ShopSettingsService(db)
    settings = await settings_service.get_settings(shop_id)
    bank_accounts = settings.get("payment", {}).get("bank_accounts", [])
    if not bank_accounts:
        raise HTTPException(400, "Shop has no bank account configured")
    
    bank_account = bank_accounts[0]  # lấy tài khoản đầu tiên
    order_code = str(order["_id"])[-8:].upper()
    qr_url = await settings_service.generate_qr_code(order_code, order["total_amount"], bank_account)
    
    if not qr_url:
        raise HTTPException(500, "Failed to generate QR code")
    
    # Lưu URL vào order để dùng lại
    await db["orders"].update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"dynamic_qr_url": qr_url}}
    )
    
    return {"qr_code_url": qr_url}