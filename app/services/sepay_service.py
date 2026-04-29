import json
from typing import Dict, Any, Optional
from datetime import datetime
import re
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class SePayService:
    def __init__(self, db):
        self.db = db
        self.order_collection = db["orders"]
        self.payment_collection = db["payments"]
    
    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Xử lý webhook từ SePay (KHÔNG xác thực)"""
        try:
            logger.info(f"Processing SePay webhook: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # ✅ LẤY ĐÚNG FIELD TỪ SEPAY
            # SePay gửi: amount_in, content, id, ...
            amount = float(data.get("transferAmount", 0))
            description = data.get("content", "")  # Nội dung chuyển khoản
            transaction_id = str(data.get("id", ""))
            gateway = data.get("gateway", "Unknown")
            account_number = data.get("account_number", "")
            transaction_date = data.get("transactionDate", "")
            
            # Kiểm tra số tiền hợp lệ
            if amount <= 0:
                logger.warning(f"Invalid amount: {amount}")
                return {"status": "error", "message": "Invalid amount"}
            
            # ✅ TRÍCH XUẤT ORDER_CODE từ nội dung
            # Nội dung mẫu: "CT DEN:580T26411K9QZB SEVQR 64C9C653"
            # Cần tìm code 8 ký tự sau SEVQR
            
            order_code = None
            
            # Cách 1: Tìm SEVQR + 8 ký tự
            sevqr_match = re.search(r'SEVQR\s+([A-Z0-9]{8})', description, re.IGNORECASE)
            if sevqr_match:
                order_code = sevqr_match.group(1).upper()
                logger.info(f"Found order_code via SEVQR: {order_code}")
            
            # Cách 2: Tìm 8 ký tự cuối (fallback)
            if not order_code:
                # Lấy 8 ký tự cuối của description (chỉ lấy chữ/số)
                clean_desc = re.sub(r'[^A-Z0-9]', '', description.upper())
                if len(clean_desc) >= 8:
                    order_code = clean_desc[-8:]
                    logger.info(f"Fallback order_code from end: {order_code}")
            
            if not order_code:
                logger.error(f"Cannot extract order_code from: {description}")
                return {"status": "error", "message": "Cannot extract order code"}
            
            # ✅ TÌM ORDER
            order = await self.order_collection.find_one({
                "$or": [
                    {"order_code": order_code},
                    {"order_code": {"$regex": f".*{order_code}", "$options": "i"}}
                ],
                "payment_status": {"$ne": "paid"}
            })
            
            # Fallback: tìm theo _id (8 ký tự cuối)
            if not order and len(order_code) == 24:
                try:
                    order = await self.order_collection.find_one({
                        "_id": ObjectId(order_code),
                        "payment_status": {"$ne": "paid"}
                    })
                    if order:
                        logger.info(f"Found order by _id: {order_code}")
                except:
                    pass
            
            if not order:
                logger.warning(f"Order not found for code: {order_code}")
                return {"status": "error", "message": f"Order not found: {order_code}"}
            
            # ✅ KIỂM TRA SỐ TIỀN
            expected_amount = order.get("total_amount", 0)
            
            if amount < expected_amount:
                logger.warning(f"Amount insufficient: received {amount}, expected {expected_amount}")
                return {"status": "error", "message": f"Insufficient amount: {amount} < {expected_amount}"}
            
            # ✅ CẬP NHẬT ĐƠN HÀNG
            update_result = await self.order_collection.update_one(
                {"_id": order["_id"]},
                {
                    "$set": {
                        "payment_status": "paid",
                        "status": "paid",
                        "paid_at": datetime.utcnow(),
                        "transaction_id": transaction_id,
                        "payment_gateway": gateway,
                        "payment_amount": amount,
                        "sepay_webhook_data": {
                            "id": transaction_id,
                            "amount": amount,
                            "content": description,
                            "gateway": gateway,
                            "transaction_date": transaction_date,
                            "received_at": datetime.utcnow().isoformat()
                        }
                    }
                }
            )
            
            if update_result.modified_count == 0:
                logger.error(f"Failed to update order {order_code}")
                return {"status": "error", "message": "Failed to update order"}
            
            logger.info(f"✅ Payment successful for order {order_code}: {amount:,.0f}đ")
            
            # ✅ GỬI THÔNG BÁO
            try:
                from app.services.notification_service import NotificationService
                noti_service = NotificationService(self.db)
                await noti_service.create_notification(
                    user_id=str(order["user_id"]),
                    type="payment",
                    title="Thanh toán thành công ✅",
                    message=f"Đơn hàng #{order_code} đã thanh toán {amount:,.0f}đ thành công",
                    reference_id=str(order["_id"])
                )
                logger.info(f"Notification sent for order {order_code}")
            except Exception as noti_error:
                logger.error(f"Failed to send notification: {noti_error}")
            
            return {"status": "success", "message": "Order paid successfully", "order_code": order_code}
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    async def generate_qr_code(self, order_id: str, order_code: str, amount: float) -> Optional[str]:
        """Tạo URL QR code thanh toán (DÙNG CHO VIETINBANK)"""
        from app.core.config import settings
        
        bank_bin = settings.BANK_BIN or "970415"
        bank_number = settings.BANK_NUMBER
        bank_name = settings.BANK_NAME
        
        if not bank_number:
            logger.warning("BANK_NUMBER not configured")
            return None
        
        # ⚠️ QUAN TRỌNG: Nội dung phải bắt đầu bằng SEVQR
        transfer_content = f"SEVQR {order_code}"
        
        # URL QR Code theo chuẩn VietQR
        qr_url = f"https://img.vietqr.io/image/{bank_bin}-{bank_number}-compact.png"
        params = f"?amount={int(amount)}&addInfo={transfer_content}"
        
        if bank_name:
            params += f"&accountName={bank_name}"
        
        full_url = qr_url + params
        
        # Lưu vào order
        await self.order_collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "qr_code_url": full_url,
                "transfer_content": transfer_content
            }}
        )
        
        logger.info(f"✅ QR generated: {transfer_content}")
        return full_url