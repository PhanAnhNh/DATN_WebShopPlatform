from typing import Dict, Any, Optional, List, Set
import asyncio
import logging
from bson import ObjectId
from datetime import datetime
from app.models.orders_model import OrderStatus
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.sepay_service import SePayService
from app.services.shipping_unit_service import ShippingUnitService

logger = logging.getLogger(__name__)


class OrderService:

    def __init__(self, db):
        self.db = db
        self.collection = db["orders"]
        self.product_collection = db["products"]
        self.shop_collection = db["shops"]
        self.cart_collection = db["carts"]
        self.variant_collection = db["product_variants"]
        self.user_collection = db["users"]
        self.notification_service = NotificationService(db)
        self.shipping_unit_service = ShippingUnitService(db)
        self.email_service = EmailService()
        
        # Cache for shipping unit
        self._shipping_unit_cache = {}

    async def _get_shipping_unit_cached(self, shipping_unit_id: str):
        """Get shipping unit with cache"""
        if shipping_unit_id in self._shipping_unit_cache:
            return self._shipping_unit_cache[shipping_unit_id]
        
        shipping_unit = await self.db["shipping_units"].find_one(
            {"_id": ObjectId(shipping_unit_id)}
        )
        
        if shipping_unit:
            self._shipping_unit_cache[shipping_unit_id] = shipping_unit
        
        return shipping_unit

    def _prepare_response(self, order: dict, order_id: str, order_code: str) -> dict:
        """Prepare fast response for client"""
        return {
            "_id": order_id,
            "order_code": order_code,
            "total_amount": order.get("total_amount", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "created_at": order.get("created_at"),
            "message": "Đặt hàng thành công"
        }

    async def create_order(self, user_id: str, order_data: dict) -> Dict[str, Any]:
        start_time = datetime.utcnow()
        
        # Get user info
        customer = await self.user_collection.find_one(
            {"_id": ObjectId(user_id)},
            {"email": 1, "full_name": 1, "username": 1}
        )
        customer_email = customer.get("email") if customer else None
        customer_name = customer.get("full_name") or customer.get("username", "Khách hàng")
        
        shop_ids: Set[str] = set()
        items_to_save: List[dict] = []
        
        # === STOCK CHECK & RESERVE ===
        for item in order_data["items"]:
            shop_ids.add(item["shop_id"])
            
            if item.get("variant_id"):
                variant_id = ObjectId(item["variant_id"])
                variant = await self.variant_collection.find_one(
                    {"_id": variant_id, "stock": {"$gte": item["quantity"]}}
                )
                if not variant:
                    raise Exception(f"Sản phẩm {item.get('product_name', '')} không đủ hàng")
                
                await self.variant_collection.update_one(
                    {"_id": variant_id},
                    {"$inc": {"stock": -item["quantity"]}}
                )
                price = item.get("price", 0)
            else:
                product_id = ObjectId(item["product_id"])
                product = await self.product_collection.find_one(
                    {"_id": product_id, "stock": {"$gte": item["quantity"]}}
                )
                if not product:
                    raise Exception(f"Sản phẩm {item.get('product_name', '')} không đủ hàng")
                
                await self.product_collection.update_one(
                    {"_id": product_id},
                    {"$inc": {"stock": -item["quantity"]}}
                )
                price = item.get("price", 0)
            
            items_to_save.append({
                "product_id": ObjectId(item["product_id"]),
                "variant_id": ObjectId(item["variant_id"]) if item.get("variant_id") else None,
                "shop_id": ObjectId(item["shop_id"]),
                "quantity": item["quantity"],
                "price": price,
                "variant_name": item.get("variant_name", ""),
                "product_name": item.get("product_name", "")
            })
        
        # Address
        shipping_addr = order_data["shipping_address"]
        formatted_address = shipping_addr.get("full_address") or \
            f"{shipping_addr['street']}, {shipping_addr['ward']}, {shipping_addr['district']}, {shipping_addr['city']}, {shipping_addr['country']}"
        
        # ✅ Tạo order doc với order_code
        order = {
            "user_id": ObjectId(user_id),
            "items": items_to_save,
            "total_amount": order_data["total_amount"],
            "subtotal": order_data["subtotal"],
            "discount": order_data["discount"],
            "shipping_fee": order_data["shipping_fee"],
            "shipping_address": formatted_address,
            "shipping_address_details": shipping_addr,
            "note": order_data.get("note", ""),
            "payment_method": order_data["payment_method"],
            "payment_status": "unpaid",
            "status": OrderStatus.pending.value,
            "created_at": datetime.utcnow(),
            "notification_sent": False,
            "email_sent": False,
            # ✅ THÊM CÁC FIELD MỚI CHO SePay
            "order_code": None,  # sẽ set sau khi có _id
            "qr_code_url": None,  # sẽ set sau nếu bank transfer
            "transaction_id": None,
            "paid_at": None
        }
        
        # INSERT order
        result = await self.collection.insert_one(order)
        order_id = str(result.inserted_id)
        order_code = order_id[-8:].upper()
        
        # ✅ CẬP NHẬT order_code vào document
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"order_code": order_code}}
        )
        
        # ✅ NẾU LÀ BANK TRANSFER, TẠO QR CODE NGAY
        qr_code_url = None
        if order_data["payment_method"] == "bank":

            sepay_service = SePayService(self.db)
            
            # Tạo nội dung chuyển khoản đúng format
            transfer_content = f"SEVQR {order_code}"
            
            qr_code_url = await sepay_service.generate_qr_code(
                order_id, 
                transfer_content,  # Truyền cả content thay vì chỉ order_code
                order_data["total_amount"]
            )
        
        # 🧹 Xoá giỏ hàng (background)
        asyncio.create_task(self._delete_cart_async(user_id))
        
        # 📦 RESPONSE TRẢ NGAY
        response_order = self._prepare_response(order, order_id, order_code)
        if qr_code_url:
            response_order["qr_code_url"] = qr_code_url  # ✅ THÊM QR URL VÀO RESPONSE
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✅ Order {order_code} created in {elapsed:.3f}s")
        
        # 🔄 BACKGROUND TASKS
        asyncio.create_task(self._update_sold_quantity_async(items_to_save, "increase"))
        
        asyncio.create_task(self._send_notifications_then_emails(
            user_id=user_id,
            customer_name=customer_name,
            order_id=order_id,
            order_code=order_code,
            shop_ids=shop_ids,
            customer_email=customer_email,
            customer_name_for_email=customer_name,
            order_data=order_data,
            items=items_to_save
        ))
        
        return response_order


    # ✅ THÊM METHOD MỚI ĐỂ CẬP NHẬT THANH TOÁN TỪ WEBHOOK
    async def update_payment_from_webhook(self, order_id: str, transaction_id: str, amount: float, raw_data: dict):
        """Update order payment status from SePay webhook"""
        try:
            order = await self.collection.find_one({"_id": ObjectId(order_id)})
            if not order:
                return False, "Order not found"
            
            if order.get("payment_status") == "paid":
                return True, "Already paid"  # Không lỗi, chỉ bỏ qua
            
            # Cập nhật order
            await self.collection.update_one(
                {"_id": ObjectId(order_id)},
                {
                    "$set": {
                        "payment_status": "paid",
                        "status": OrderStatus.paid.value,
                        "paid_at": datetime.utcnow(),
                        "transaction_id": transaction_id,
                        "webhook_data": raw_data  # lưu lại để debug
                    }
                }
            )
            
            # Tạo notification thanh toán thành công
            await self.notification_service.create_notification(
                user_id=str(order["user_id"]),
                type="payment",
                title="Thanh toán thành công ✅",
                message=f"Đơn hàng #{order_id[-8:].upper()} đã thanh toán {amount:,.0f}đ thành công",
                reference_id=order_id
            )
            
            logger.info(f"✅ Payment updated for order {order_id[-8:].upper()}")
            return True, "Success"
            
        except Exception as e:
            logger.error(f"Failed to update payment: {e}")
            return False, str(e)
    
    async def _delete_cart_async(self, user_id: str):
        """Delete cart safely in background"""
        try:
            await self.cart_collection.delete_one({"user_id": ObjectId(user_id)})
            logger.info(f"🧹 Cart deleted for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Delete cart failed: {e}")

    async def _send_notifications_async(
        self, 
        user_id: str, 
        customer_name: str, 
        order_id: str, 
        order_code: str, 
        shop_ids: Set[str]
    ):
        """Send notifications in background - PRIORITY 1"""
        try:
            # Send to customer
            await self.notification_service.create_notification(
                user_id=user_id,
                type="order",
                title="Đặt hàng thành công 🎉",
                message=f"Đơn hàng #{order_code} đã được đặt thành công",
                reference_id=order_id
            )
            
            # Send to shops
            for shop_id in shop_ids:
                await self.notification_service.create_notification(
                    user_id=shop_id,
                    type="order",
                    title="Đơn hàng mới 🛒",
                    message=f"Có đơn hàng mới #{order_code} cần xử lý",
                    reference_id=order_id
                )
            
            # Update order with notification status
            await self.collection.update_one(
                {"_id": ObjectId(order_id)},
                {"$set": {"notification_sent": True, "notification_sent_at": datetime.utcnow()}}
            )
            
            logger.info(f"✅ Notifications sent for order {order_code}")
        except Exception as e:
            logger.error(f"❌ Failed to send notifications for order {order_code}: {e}")

    async def _send_emails_async(
        self,
        customer_email: str,
        customer_name: str,
        order_id: str,
        order_code: str,
        order_data: dict,
        items: list,
        shop_ids: Set[str]
    ):
        """Send emails in background - PRIORITY 2 (after notifications)"""
        try:
            # Send customer email
            await self._send_customer_order_email(
                customer_email, customer_name, order_id, order_code, order_data, items
            )
            
            # Send shop emails
            for shop_id in shop_ids:
                await self._send_shop_order_email(shop_id, order_id, order_code, order_data, items)
            
            # Update order with email status
            await self.collection.update_one(
                {"_id": ObjectId(order_id)},
                {"$set": {"email_sent": True, "email_sent_at": datetime.utcnow()}}
            )
            
            logger.info(f"✅ Emails sent for order {order_code}")
        except Exception as e:
            logger.error(f"❌ Failed to send emails for order {order_code}: {e}")

    async def _update_sold_quantity_async(self, items: list, operation: str = "increase"):
        """Update sold quantity in background"""
        try:
            change = 1 if operation == "increase" else -1
            for item in items:
                product_id = item["product_id"]
                quantity = item["quantity"] * change
                
                await self.db["products"].update_one(
                    {"_id": product_id},
                    {"$inc": {"sold_quantity": quantity}}
                )
                
                if item.get("variant_id"):
                    await self.db["product_variants"].update_one(
                        {"_id": item["variant_id"]},
                        {"$inc": {"sold_quantity": quantity}}
                    )
            logger.info(f"✅ Sold quantity updated ({operation})")
        except Exception as e:
            logger.error(f"❌ Failed to update sold quantity: {e}")

    async def _send_customer_order_email(
        self, 
        customer_email: str, 
        customer_name: str, 
        order_id: str, 
        order_code: str, 
        order_data: dict, 
        items: list
    ):
        """Send customer order confirmation email"""
        subject = f"Xác nhận đơn hàng #{order_code} - Đặc Sản Quê Tôi"
        
        # Build items HTML
        items_html = ""
        for item in items:
            items_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{item.get('product_name', 'Sản phẩm')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item.get('quantity', 1)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{self._format_currency(item.get('price', 0))}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{self._format_currency(item.get('price', 0) * item.get('quantity', 1))}</td>
            </tr>
            """
        
        payment_method_text = {
            "cod": "Thanh toán khi nhận hàng (COD)",
            "bank": "Chuyển khoản ngân hàng",
            "momo": "Ví MoMo",
            "vnpay": "VNPay",
            "zalopay": "ZaloPay"
        }.get(order_data.get("payment_method"), order_data.get("payment_method"))
        
        shipping_addr = order_data["shipping_address"]
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #f5eee1; }}
                .header {{ background: #2e7d32; color: white; padding: 20px; text-align: center; }}
                .content {{ background: white; padding: 30px; }}
                .order-info {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #2e7d32; color: white; padding: 10px; text-align: left; }}
                .total {{ font-size: 18px; font-weight: bold; text-align: right; margin-top: 15px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #777; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Đặc Sản Quê Tôi</h2>
                    <p>Xác nhận đơn hàng</p>
                </div>
                <div class="content">
                    <h3>Xin chào {customer_name},</h3>
                    <p>Cảm ơn bạn đã đặt hàng tại <strong>Đặc Sản Quê Tôi</strong>!</p>
                    
                    <div class="order-info">
                        <p><strong>📋 Mã đơn hàng:</strong> #{order_code}</p>
                        <p><strong>📅 Ngày đặt:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        <p><strong>💳 Phương thức thanh toán:</strong> {payment_method_text}</p>
                        <p><strong>📍 Địa chỉ giao hàng:</strong> {shipping_addr.get('street', '')}, {shipping_addr.get('ward', '')}, {shipping_addr.get('district', '')}, {shipping_addr.get('city', '')}</p>
                    </div>
                    
                    <h4>Chi tiết đơn hàng:</h4>
                    <table>
                        <thead>
                            <tr><th>Sản phẩm</th><th>Số lượng</th><th>Đơn giá</th><th>Thành tiền</th></tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                    
                    <div class="total">
                        <p>Tạm tính: {self._format_currency(order_data['subtotal'])}</p>
                        <p>Phí vận chuyển: {self._format_currency(order_data['shipping_fee'])}</p>
                        {f'<p>Giảm giá: -{self._format_currency(order_data["discount"])}</p>' if order_data.get('discount') else ''}
                        <p><strong>Tổng cộng: {self._format_currency(order_data['total_amount'])}</strong></p>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2024 Đặc Sản Quê Tôi</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await self.email_service.send_email(customer_email, subject, html_content)

    async def _send_shop_order_email(
        self, 
        shop_id: str, 
        order_id: str, 
        order_code: str, 
        order_data: dict, 
        all_items: list
    ):
        """Send shop order notification email"""
        shop = await self.shop_collection.find_one({"_id": ObjectId(shop_id)})
        shop_email = shop.get("email") if shop else None
        shop_name = shop.get("name", "Cửa hàng") if shop else "Cửa hàng"
        
        if not shop_email:
            return
        
        # Filter items for this shop
        shop_items = [item for item in all_items if str(item["shop_id"]) == shop_id]
        
        if not shop_items:
            return
        
        items_html = ""
        for item in shop_items:
            items_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{item.get('product_name', 'Sản phẩm')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item.get('quantity', 1)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{self._format_currency(item.get('price', 0))}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{self._format_currency(item.get('price', 0) * item.get('quantity', 1))}</td>
            </tr>
            """
        
        shop_total = sum(item.get('price', 0) * item.get('quantity', 1) for item in shop_items)
        shipping_addr = order_data["shipping_address"]
        
        subject = f"[ĐƠN HÀNG MỚI] #{order_code} - Đặc Sản Quê Tôi"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; background: #f5eee1; }}
                .header {{ background: #ff9800; color: white; padding: 20px; text-align: center; }}
                .content {{ background: white; padding: 30px; }}
                .order-info {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #ff9800; color: white; padding: 10px; text-align: left; }}
                .total {{ font-size: 18px; font-weight: bold; text-align: right; margin-top: 15px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #777; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Đặc Sản Quê Tôi</h2>
                    <p>Thông báo đơn hàng mới</p>
                </div>
                <div class="content">
                    <h3>Xin chào {shop_name},</h3>
                    <p>Có đơn hàng mới cần xử lý!</p>
                    
                    <div class="order-info">
                        <p><strong>📋 Mã đơn hàng:</strong> #{order_code}</p>
                        <p><strong>👤 Khách hàng:</strong> {shipping_addr.get('name', '')}</p>
                        <p><strong>📞 SĐT:</strong> {shipping_addr.get('phone', '')}</p>
                        <p><strong>📍 Địa chỉ:</strong> {shipping_addr.get('street', '')}, {shipping_addr.get('ward', '')}, {shipping_addr.get('district', '')}, {shipping_addr.get('city', '')}</p>
                    </div>
                    
                    <h4>Sản phẩm:</h4>
                    <table>
                        <thead>
                            <tr><th>Sản phẩm</th><th>Số lượng</th><th>Đơn giá</th><th>Thành tiền</th></tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                    
                    <div class="total">
                        <p><strong>Tổng: {self._format_currency(shop_total)}</strong></p>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2024 Đặc Sản Quê Tôi</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await self.email_service.send_email(shop_email, subject, html_content)

    def _format_currency(self, amount: float) -> str:
        """Format currency"""
        return f"{amount:,.0f}₫".replace(",", ".")

    async def _send_notifications_then_emails(
        self,
        user_id: str,
        customer_name: str,
        order_id: str,
        order_code: str,
        shop_ids: set,
        customer_email: str,
        customer_name_for_email: str,
        order_data: dict,
        items: list
    ):
        """Gửi notifications trước, sau đó mới gửi email (cả hai đều background)"""
        try:
            # 1. Gửi notifications (nhanh)
            await self._send_notifications_async(
                user_id, customer_name, order_id, order_code, shop_ids
            )
            # 2. Sau đó gửi emails (chậm, nhưng không block do thread pool)
            if customer_email:
                await self._send_emails_async(
                    customer_email, customer_name_for_email, order_id, order_code,
                    order_data, items, shop_ids
                )
            logger.info(f"✅ Notifications and emails completed for order {order_code}")
        except Exception as e:
            logger.error(f"❌ Background notification/email failed for order {order_code}: {e}")

    # ==================== OTHER METHODS ====================
    
    async def get_user_orders(self, user_id: str):
        """Get user orders list"""
        cursor = self.collection.find(
            {"user_id": ObjectId(user_id)},
            {
                "total_amount": 1, "status": 1, "payment_status": 1,
                "created_at": 1, "items.product_id": 1, "items.quantity": 1,
                "items.price": 1, "items.variant_name": 1, "items.product_name": 1
            }
        ).sort("created_at", -1)
        
        orders = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["user_id"] = str(doc["user_id"])
            doc["order_code"] = str(doc["_id"])[-8:].upper()
            for item in doc.get("items", []):
                item["product_id"] = str(item["product_id"])
                if item.get("variant_id"):
                    item["variant_id"] = str(item["variant_id"])
            orders.append(doc)
        
        return orders

    async def get_order(self, order_id: str):
        """Get order detail"""
        try:
            order = await self.collection.find_one({"_id": ObjectId(order_id)})
            if not order:
                return None
            result = self._prepare_full_response(order)
            result["order_code"] = order_id[-8:].upper()
            return result
        except:
            return None
        
    def _prepare_full_response(self, order: dict) -> dict:
        """Prepare full order response"""
        result = {
            "_id": str(order["_id"]),
            "user_id": str(order["user_id"]),
            "total_amount": order.get("total_amount", 0),
            "subtotal": order.get("subtotal", 0),
            "discount": order.get("discount", 0),
            "shipping_fee": order.get("shipping_fee", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "payment_method": order.get("payment_method", "cod"),
            "shipping_address": order.get("shipping_address", ""),
            "shipping_address_details": order.get("shipping_address_details", {}),
            "note": order.get("note", ""),
            "created_at": order.get("created_at"),
            "items": [
                {
                    "product_id": str(item["product_id"]),
                    "shop_id": str(item["shop_id"]),
                    "quantity": item["quantity"],
                    "price": item["price"],
                    "variant_id": str(item["variant_id"]) if item.get("variant_id") else None,
                    "variant_name": item.get("variant_name", ""),
                    "product_name": item.get("product_name", "")
                }
                for item in order.get("items", [])
            ]
        }
        
        if order.get("voucher"):
            result["voucher"] = {
                "id": str(order["voucher"]["id"]),
                "code": order["voucher"]["code"],
                "discount": order["voucher"]["discount"]
            }
        
        if order.get("shipping_unit"):
            result["shipping_unit"] = order["shipping_unit"]
        
        return result

    async def update_order_status(self, order_id: str, status: OrderStatus):
        """Update order status"""
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": status.value}}
        )
        return await self.get_order(order_id)
    
    async def _safe_db_op(self, coro, action: str = "db_op"):
        """Wrapper để chạy DB operation trong background"""
        try:
            await coro
        except Exception as e:
            logger.error(f"❌ Background {action} failed: {e}")
    
    async def update_payment_status(self, order_id: str, status: str):
        """Update payment status"""
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"payment_status": status}}
        )
        return await self.get_order(order_id)

    async def cancel_order(self, order_id: str, user_id: str, cancel_reason: str = None):
        """Cancel order and restore stock"""
        try:
            order = await self.collection.find_one({
                "_id": ObjectId(order_id),
                "user_id": ObjectId(user_id)
            })
        except:
            raise Exception("Không tìm thấy đơn hàng")
        
        if not order:
            raise Exception("Không tìm thấy đơn hàng")
        
        if order["status"] not in [OrderStatus.pending.value, OrderStatus.paid.value]:
            raise Exception("Không thể hủy đơn hàng ở trạng thái này")
        
        # Restore stock
        for item in order.get("items", []):
            if item.get("variant_id"):
                await self.db["product_variants"].update_one(
                    {"_id": item["variant_id"]},
                    {"$inc": {"stock": item["quantity"]}}
                )
            else:
                await self.db["products"].update_one(
                    {"_id": item["product_id"]},
                    {"$inc": {"stock": item["quantity"]}}
                )
        
        # Update order status
        update_data = {
            "status": OrderStatus.cancelled.value, 
            "cancelled_at": datetime.utcnow()
        }
        if cancel_reason:
            update_data["cancel_reason"] = cancel_reason
        
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": update_data}
        )
        
        # Update sold quantity in background
        asyncio.create_task(self._update_sold_quantity_async(
            order.get("items", []), "decrease"
        ))
        
        return {"status": "success", "message": "Đơn hàng đã được hủy và hoàn kho", "refund_amount": order.get("total_amount", 0)}