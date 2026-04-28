# app/services/sepay_service.py
import json
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
        """Xử lý webhook từ SePay"""
        try:
            logger.info(f"Processing SePay webhook: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Lấy thông tin từ webhook
            description = data.get("description", "").strip()
            amount = float(data.get("amount_in", 0))
            transaction_id = str(data.get("id", ""))
            
            # Loại bỏ prefix SEVQR để lấy order_code
            import re
            clean_desc = re.sub(r'^SEVQR\s+', '', description, flags=re.IGNORECASE).strip()
            order_code = clean_desc.upper()
            
            logger.info(f"Extracted order_code: {order_code} from description: {description}")
            
            # Tìm order
            order = await self.order_collection.find_one({
                "order_code": order_code,
                "payment_status": {"$ne": "paid"}
            })
            
            if not order:
                # Thử tìm theo _id
                try:
                    if len(order_code) == 24:
                        order = await self.order_collection.find_one({
                            "_id": ObjectId(order_code),
                            "payment_status": {"$ne": "paid"}
                        })
                except:
                    pass
            
            if not order:
                logger.warning(f"Order not found for code: {order_code}")
                return {"status": "error", "message": "Order not found"}
            
            # Kiểm tra số tiền
            order_amount = order.get("total_amount", 0)
            if amount < order_amount:
                logger.warning(f"Amount mismatch: {amount} < {order_amount}")
                return {"status": "error", "message": f"Insufficient amount"}
            
            # Cập nhật thanh toán
            await self.order_collection.update_one(
                {"_id": order["_id"]},
                {
                    "$set": {
                        "payment_status": "paid",
                        "status": "paid",
                        "paid_at": datetime.utcnow(),
                        "transaction_id": transaction_id,
                        "webhook_data": data
                    }
                }
            )
            
            # Tạo notification
            from app.services.notification_service import NotificationService
            noti_service = NotificationService(self.db)
            await noti_service.create_notification(
                user_id=str(order["user_id"]),
                type="payment",
                title="Thanh toán thành công",
                message=f"Đơn hàng #{order_code} đã thanh toán {amount:,.0f}đ thành công",
                reference_id=str(order["_id"])
            )
            
            logger.info(f"Payment processed for order {order_code}")
            
            return {"status": "success", "message": "Order paid successfully"}
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    async def _find_order_by_code(self, description: str) -> Optional[Dict]:
        """
        Tìm order theo nội dung chuyển khoản
        """
        # SePay sẽ gửi description có dạng: "SEVQR C6687621"
        # Cần loại bỏ prefix "SEVQR" để lấy order_code
        import re
        
        # Loại bỏ prefix SEVQR (có thể viết hoa hoặc thường)
        clean_desc = re.sub(r'^SEVQR\s+', '', description, flags=re.IGNORECASE).strip()
        
        # Tìm order_code (8 ký tự cuối của _id)
        order_code = clean_desc.upper()
        
        logger.info(f"🔍 Looking for order with code: {order_code} (from description: {description})")
        
        # Cách 1: Tìm theo field order_code
        order = await self.order_collection.find_one({"order_code": order_code})
        if order:
            return order
        
        # Cách 2: Tìm theo 8 ký tự cuối của _id (fallback)
        orders = await self.order_collection.find({
            "payment_status": {"$ne": "paid"},
            "status": {"$ne": "cancelled"}
        }).to_list(100)
        
        for order in orders:
            if str(order["_id"])[-8:].upper() == order_code:
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

    async def generate_qr_code(self, order_id: str, order_code: str, amount: float) -> Optional[str]:
        """
        Tạo URL QR code thanh toán
        """
        from app.core.config import settings
        
        bank_bin = settings.BANK_BIN or "970415"
        bank_number = settings.BANK_NUMBER
        bank_name = settings.BANK_NAME
        
        if not bank_number:
            logger.warning("BANK_NUMBER not configured")
            return None
        
        # ⚠️ QUAN TRỌNG: Thêm prefix SEVQR cho VietinBank
        # Nội dung chuyển khoản phải bắt đầu bằng SEVQR
        transfer_content = f"SEVQR {order_code}"
        
        # URL QR Code với nội dung đã sửa
        qr_url = f"https://img.vietqr.io/image/{bank_bin}-{bank_number}-compact.png"
        params = f"?amount={int(amount)}&addInfo={transfer_content}"
        
        if bank_name:
            params += f"&accountName={bank_name}"
        
        full_url = qr_url + params
        
        # Lưu URL vào order
        await self.order_collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "qr_code_url": full_url,
                "transfer_content": transfer_content  # Lưu lại để debug
            }}
        )
        
        logger.info(f"✅ QR generated with content: {transfer_content}")
        
        return full_url