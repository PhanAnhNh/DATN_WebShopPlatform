# app/services/sepay_service.py
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import hmac
import logging
from bson import ObjectId

logger = logging.getLogger(__name__)


class SePayService:
    def __init__(self, db):
        self.db = db
        self.order_collection = db["orders"]
        self.payment_collection = db["payments"]
    
    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Xử lý webhook từ SePay
        
        SePay gửi data dạng:
        {
            "id": 123456,
            "gateway": "vietinbank",
            "transaction_date": "2024-01-15 10:00:00",
            "account_number": "123456789",
            "account_name": "NGUYEN VAN A",
            "amount_in": 100000,
            "amount_out": 0,
            "accumulated": 100000,
            "code": "sepay_gateway",
            "sub_account": "123456",
            "reference_code": "REF123",
            "description": "ORD123456",
            "transaction_type": "in"
        }
        """
        try:
            # 1. Extract nội dung chuyển khoản = order_code
            description = data.get("description", "").strip()
            amount = float(data.get("amount_in", 0))
            transaction_id = str(data.get("id", ""))
            
            if amount <= 0:
                logger.warning(f"Invalid amount: {amount}")
                return {"status": "error", "message": "Invalid amount"}
            
            # 2. Tìm order theo order_code (8 ký tự cuối của _id)
            order = await self._find_order_by_code(description)
            
            if not order:
                logger.warning(f"Order not found for code: {description}")
                return {"status": "error", "message": "Order not found"}
            
            # 3. Kiểm tra trạng thái (tránh xử lý trùng)
            if order.get("payment_status") == "paid":
                logger.info(f"Order {description} already paid, skipping")
                return {"status": "success", "message": "Already processed"}
            
            # 4. Kiểm tra số tiền
            order_amount = order.get("total_amount", 0)
            if amount < order_amount:
                logger.warning(f"Amount mismatch: {amount} < {order_amount}")
                # Ghi nhận payment pending với số tiền thiếu
                await self._record_pending_payment(order, transaction_id, amount, data)
                return {"status": "error", "message": f"Insufficient amount. Need: {order_amount}, Got: {amount}"}
            
            # 5. Xử lý thanh toán thành công
            await self._process_successful_payment(order, transaction_id, amount, data)
            
            # 6. Chạy các task nền
            await self._trigger_background_tasks(order, description, amount)
            
            logger.info(f"✅ Payment processed successfully for order {description}")
            return {"status": "success", "message": "Order paid successfully"}
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _find_order_by_code(self, order_code: str) -> Optional[Dict]:
        """Tìm order theo order_code (8 ký tự cuối của _id)"""
        # Cách 1: Tìm trong field order_code nếu có
        order = await self.order_collection.find_one({"order_code": order_code})
        if order:
            return order
        
        # Cách 2: Tìm theo 8 ký tự cuối của _id (fallback)
        orders = await self.order_collection.find({
            "payment_status": {"$ne": "paid"},
            "status": {"$ne": "cancelled"}
        }).to_list(100)
        
        for order in orders:
            if str(order["_id"])[-8:].upper() == order_code.upper():
                return order
        
        return None
    
    async def _record_pending_payment(self, order: Dict, transaction_id: str, amount: float, raw_data: Dict):
        """Ghi nhận thanh toán chờ (thiếu tiền)"""
        await self.payment_collection.update_one(
            {"order_id": order["_id"], "method": "bank_transfer"},
            {
                "$set": {
                    "status": "pending",
                    "transaction_id": transaction_id,
                    "amount_received": amount,
                    "amount_expected": order.get("total_amount", 0),
                    "webhook_data": raw_data,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
    
    async def _process_successful_payment(self, order: Dict, transaction_id: str, amount: float, raw_data: Dict):
        """Xử lý thanh toán thành công"""
        # 1. Update payment record
        await self.payment_collection.update_one(
            {"order_id": order["_id"], "method": "bank_transfer"},
            {
                "$set": {
                    "status": "success",
                    "transaction_id": transaction_id,
                    "amount_paid": amount,
                    "completed_at": datetime.utcnow(),
                    "webhook_data": raw_data
                }
            },
            upsert=True
        )
        
        # 2. Update order
        await self.order_collection.update_one(
            {"_id": order["_id"]},
            {
                "$set": {
                    "payment_status": "paid",
                    "status": "paid",
                    "paid_at": datetime.utcnow(),
                    "transaction_id": transaction_id
                }
            }
        )
    
    async def _trigger_background_tasks(self, order: Dict, order_code: str, amount: float):
        """Trigger các task nền sau khi thanh toán thành công"""
        # Import ở đây để tránh circular import
        from app.services.notification_service import NotificationService
        from app.services.email_service import EmailService
        
        # Gửi notification
        noti_service = NotificationService(self.db)
        await noti_service.create_notification(
            user_id=str(order["user_id"]),
            type="payment",
            title="Thanh toán thành công ✅",
            message=f"Đơn hàng #{order_code} đã thanh toán {amount:,.0f}đ thành công",
            reference_id=str(order["_id"])
        )
        
        # Gửi email (chạy nền)
        # email_service = EmailService()
        # asyncio.create_task(email_service.send_payment_confirmation(order))
    
    async def generate_qr_code(self, order_id: str, order_code: str, amount: float) -> Optional[str]:
        """
        Tạo URL QR code thanh toán
        Sử dụng VietQR API: https://img.vietqr.io
        """
        from app.core.config import settings
        
        # Lấy thông tin ngân hàng từ settings của shop
        # Hoặc dùng config mặc định
        bank_bin = settings.BANK_BIN or "970415"  # Default VietinBank
        bank_number = settings.BANK_NUMBER
        bank_name = settings.BANK_NAME
        
        if not bank_number:
            logger.warning("BANK_NUMBER not configured")
            return None
        
        # URL QR Code (compact template)
        # https://img.vietqr.io/image/{BIN}-{ACCOUNT}-compact.png?amount={amount}&addInfo={content}
        qr_url = f"https://img.vietqr.io/image/{bank_bin}-{bank_number}-compact.png"
        params = f"?amount={int(amount)}&addInfo={order_code}"
        
        # Nếu có tên tài khoản thì thêm accountName
        if bank_name:
            params += f"&accountName={bank_name}"
        
        full_url = qr_url + params
        
        # Lưu URL vào order để dùng lại
        await self.order_collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"qr_code_url": full_url}}
        )
        
        return full_url