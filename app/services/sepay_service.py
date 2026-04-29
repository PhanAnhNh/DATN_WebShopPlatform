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
        """Xử lý webhook từ SePay"""
        try:
            logger.info(f"Processing SePay webhook: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Lấy dữ liệu từ webhook
            amount = float(data.get("transferAmount", 0))
            description = data.get("content", "")
            transaction_id = str(data.get("id", ""))
            gateway = data.get("gateway", "Unknown")
            account_number = data.get("accountNumber", "")
            transaction_date = data.get("transactionDate", "")
            reference_code = data.get("referenceCode", "")
            
            # Kiểm tra số tiền hợp lệ
            if amount <= 0:
                logger.warning(f"Invalid amount: {amount}")
                return {"status": "error", "message": "Invalid amount"}
            
            # ✅ QUAN TRỌNG: Ưu tiên lấy order_code từ content (sau SEVQR)
            order_code = None
            
            # Cách 1: Tìm SEVQR + 8 ký tự (ƯU TIÊN NHẤT)
            # Content mẫu: "CT DEN:580T2641C9402KW2 SEVQR 59C801F1"
            sevqr_match = re.search(r'SEVQR\s+([A-Z0-9]{8})', description, re.IGNORECASE)
            if sevqr_match:
                order_code = sevqr_match.group(1).upper()
                logger.info(f"✅ Found order_code from SEVQR in content: {order_code}")
            
            # Cách 2: Tìm 8 ký tự sau SEVQR (không có space)
            if not order_code:
                sevqr_match2 = re.search(r'SEVQR([A-Z0-9]{8})', description, re.IGNORECASE)
                if sevqr_match2:
                    order_code = sevqr_match2.group(1).upper()
                    logger.info(f"✅ Found order_code from SEVQR (no space): {order_code}")
            
            # Cách 3: Từ content - tìm mã 8 ký tự cuối của CT DEN
            if not order_code:
                match = re.search(r'CT DEN:([A-Z0-9]+)', description, re.IGNORECASE)
                if match:
                    raw_code = match.group(1)
                    if len(raw_code) >= 8:
                        order_code = raw_code[-8:]
                        logger.info(f"Extracted from CT DEN: {order_code}")
            
            # Cách 4: Fallback cuối - dùng referenceCode
            if not order_code and reference_code:
                if len(reference_code) >= 8:
                    order_code = reference_code[-8:]
                    logger.info(f"Fallback to reference_code last 8 chars: {order_code}")
            
            if not order_code:
                logger.error(f"Cannot extract order_code from: description={description}")
                return {"status": "error", "message": "Cannot extract order code"}
            
            logger.info(f"🔍 Searching for order with order_code: {order_code}")
            
            # TÌM ORDER - Tìm theo order_code (8 ký tự)
            order = await self.order_collection.find_one({
                "order_code": order_code,
                "payment_status": {"$ne": "paid"}
            })
            
            # Nếu không tìm thấy, thử tìm với order_code không phân biệt hoa thường
            if not order:
                order = await self.order_collection.find_one({
                    "order_code": {"$regex": f"^{order_code}$", "$options": "i"},
                    "payment_status": {"$ne": "paid"}
                })
            
            if not order:
                # Log danh sách order_code đang pending để debug
                pending_orders = await self.order_collection.find(
                    {"payment_status": {"$ne": "paid"}}
                ).limit(10).to_list(None)
                pending_codes = [o.get('order_code') for o in pending_orders]
                logger.warning(f"Order not found for code: {order_code}")
                logger.info(f"Pending order_codes in DB: {pending_codes}")
                return {"status": "error", "message": f"Order not found: {order_code}"}
            
            # KIỂM TRA SỐ TIỀN
            expected_amount = order.get("total_amount", 0)
            
            if amount < expected_amount:
                logger.warning(f"Amount insufficient: received {amount}, expected {expected_amount}")
                return {"status": "error", "message": f"Insufficient amount: {amount} < {expected_amount}"}
            
            # CẬP NHẬT ĐƠN HÀNG
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
                            "reference_code": reference_code,
                            "received_at": datetime.utcnow().isoformat()
                        }
                    }
                }
            )
            
            if update_result.modified_count == 0:
                logger.error(f"Failed to update order {order_code}")
                return {"status": "error", "message": "Failed to update order"}
            
            logger.info(f"✅ Payment successful for order {order_code}: {amount:,.0f}đ")
            
            # GỬI THÔNG BÁO
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
        """Tạo URL QR code thanh toán"""
        from app.core.config import settings
        
        bank_bin = settings.BANK_BIN or "970415"
        bank_number = settings.BANK_NUMBER
        bank_name = settings.BANK_NAME
        
        if not bank_number:
            logger.warning("BANK_NUMBER not configured")
            return None
        
        # Nội dung chuyển khoản - đảm bảo SEVQR + space + order_code
        transfer_content = f"SEVQR {order_code}"
        
        qr_url = f"https://img.vietqr.io/image/{bank_bin}-{bank_number}-compact.png"
        params = f"?amount={int(amount)}&addInfo={transfer_content}"
        
        if bank_name:
            params += f"&accountName={bank_name}"
        
        full_url = qr_url + params
        
        await self.order_collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "qr_code_url": full_url,
                "transfer_content": transfer_content,
                "order_code": order_code
            }}
        )
        
        logger.info(f"✅ QR generated for order_code: {order_code}")
        return full_url