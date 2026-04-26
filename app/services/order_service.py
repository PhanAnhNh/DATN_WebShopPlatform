from typing import Dict, Any, Optional
import asyncio
import logging
from bson import ObjectId
from datetime import datetime
from app import db
from app.models.orders_model import OrderStatus
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
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
        
        # Cache cho shipping unit
        self._shipping_unit_cache = {}
        
        # Queue cho background tasks
        self._background_tasks = set()

    async def _get_shipping_unit_cached(self, shipping_unit_id: str):
        """Lấy thông tin shipping unit với cache"""
        if shipping_unit_id in self._shipping_unit_cache:
            return self._shipping_unit_cache[shipping_unit_id]
        
        # Giả sử có collection shipping_units
        shipping_unit = await self.db["shipping_units"].find_one(
            {"_id": ObjectId(shipping_unit_id)}
        )
        
        if shipping_unit:
            self._shipping_unit_cache[shipping_unit_id] = shipping_unit
        
        return shipping_unit

    def _prepare_response(self, order: dict, order_id: str, order_code: str) -> dict:
        """Chuẩn bị response nhanh cho client"""
        return {
            "_id": order_id,
            "order_code": order_code,
            "total_amount": order.get("total_amount", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "created_at": order.get("created_at"),
            "message": "Đặt hàng thành công"
        }

    # app/services/order_service.py

    async def create_order(self, user_id: str, order_data: dict) -> Dict[str, Any]:
        """
        Tạo đơn hàng - Tối ưu cho tốc độ < 2 giây
        """
        start_time = datetime.utcnow()
        
        # Lấy thông tin user
        customer = await self.user_collection.find_one(
            {"_id": ObjectId(user_id)},
            {"email": 1, "full_name": 1, "username": 1}
        )
        customer_email = customer.get("email") if customer else None
        customer_name = customer.get("full_name") or customer.get("username", "Khách hàng")
        
        shop_ids = set()
        items_to_save = []
        total_price = 0
        
        # Kiểm tra và update stock
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
            
            total_price += price * item["quantity"]
            items_to_save.append({
                "product_id": ObjectId(item["product_id"]),
                "variant_id": ObjectId(item["variant_id"]) if item.get("variant_id") else None,
                "shop_id": ObjectId(item["shop_id"]),
                "quantity": item["quantity"],
                "price": price,
                "variant_name": item.get("variant_name", ""),
                "product_name": item.get("product_name", "")
            })
        
        # Format shipping address
        shipping_addr = order_data["shipping_address"]
        formatted_address = shipping_addr.get("full_address") or \
            f"{shipping_addr['street']}, {shipping_addr['ward']}, {shipping_addr['district']}, {shipping_addr['city']}, {shipping_addr['country']}"
        
        # Tạo order object
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
            "created_at": datetime.utcnow()
        }
        
        # Thêm shipping unit nếu có
        if order_data.get("shipping_unit_id"):
            shipping_unit = await self._get_shipping_unit_cached(order_data["shipping_unit_id"])
            if shipping_unit:
                order["shipping_unit"] = {
                    "id": str(shipping_unit["_id"]),
                    "name": shipping_unit["name"],
                    "code": shipping_unit["code"],
                    "shipping_fee": order_data["shipping_fee"],
                    "estimated_delivery_days": shipping_unit.get("estimated_delivery_days", 3)
                }
                order["shipping_unit_id"] = ObjectId(order_data["shipping_unit_id"])
        
        # Thêm voucher
        if order_data.get("voucher"):
            order["voucher"] = {
                "id": ObjectId(order_data["voucher"]["id"]),
                "code": order_data["voucher"]["code"],
                "discount": order_data["voucher"]["discount"]
            }
        
        # Insert order
        result = await self.collection.insert_one(order)
        order_id = str(result.inserted_id)
        order_code = order_id[-8:].upper()
        
        # ====== QUAN TRỌNG: BỎ AWAIT TRƯỚC create_task ======
        # Clear cart (async, không block)
        asyncio.create_task(self.cart_collection.delete_one({"user_id": ObjectId(user_id)}))
        
        # Response
        response_order = self._prepare_response(order, order_id, order_code)
        
        # Background tasks - KHÔNG await
        asyncio.create_task(self._create_notifications_background(
            user_id, customer_name, order_id, order_code, shop_ids
        ))
        
        if customer_email:
            asyncio.create_task(self._send_customer_email_background(
                customer_email, customer_name, order_id, order_code, order_data, items_to_save
            ))
        
        asyncio.create_task(self._send_shop_emails_background(
            shop_ids, order_id, order_code, order_data, items_to_save
        ))
        
        asyncio.create_task(self._update_product_sold_quantity_background(items_to_save, "increase"))
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Order {order_code} created in {elapsed:.3f}s")
        
        return response_order


    async def _send_customer_email_background(
        self, customer_email: str, customer_name: str, order_id: str, 
        order_code: str, order_data: dict, items: list
    ):
        """Gửi email customer trong background"""
        try:
            await self._send_customer_order_email(
                customer_email, customer_name, order_id, order_code, order_data, items
            )
            logger.info(f"✅ Customer email sent for order {order_code}")
        except Exception as e:
            logger.error(f"❌ Failed to send customer email: {e}")

    async def _create_notifications_background(
        self, user_id: str, customer_name: str, order_id: str, order_code: str, shop_ids: set
    ):
        """Tạo thông báo trong background"""
        try:
            # Thông báo cho customer
            await self.notification_service.create_notification(
                user_id=user_id,
                type="order",
                title="Đặt hàng thành công 🎉",
                message=f"Đơn hàng #{order_code} đã được đặt thành công",
                reference_id=order_id
            )
            
            # Thông báo cho các shop
            for shop_id in shop_ids:
                await self.notification_service.create_notification(
                    user_id=shop_id,
                    type="order",
                    title="Đơn hàng mới 🛒",
                    message=f"Có đơn hàng mới #{order_code} cần xử lý",
                    reference_id=order_id
                )
            logger.info(f"✅ Notifications created for order {order_code}")
        except Exception as e:
            logger.error(f"❌ Failed to create notifications: {e}")

    async def _send_shop_emails_background(
        self, shop_ids: set, order_id: str, order_code: str, order_data: dict, all_items: list
    ):
        """Gửi email shops trong background"""
        try:
            for shop_id in shop_ids:
                await self._send_shop_order_email(shop_id, order_id, order_code, order_data, all_items)
            logger.info(f"✅ Shop emails sent for order {order_code}")
        except Exception as e:
            logger.error(f"❌ Failed to send shop emails: {e}")

    async def _update_product_sold_quantity_background(self, items: list, operation: str = "increase"):
        """Update sold quantity trong background"""
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
        self, customer_email: str, customer_name: str, order_id: str, 
        order_code: str, order_data: dict, items: list
    ):
        """Gửi email xác nhận đơn hàng cho khách hàng"""
        subject = f"Xác nhận đơn hàng #{order_code} - Đặc Sản Quê Tôi"
        
        # Tạo danh sách sản phẩm trong email
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
                .order-info p {{ margin: 5px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th {{ background: #2e7d32; color: white; padding: 10px; text-align: left; }}
                .total {{ font-size: 18px; font-weight: bold; text-align: right; margin-top: 15px; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #777; }}
                .btn {{ display: inline-block; padding: 10px 20px; background: #2e7d32; color: white; text-decoration: none; border-radius: 5px; }}
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
                    <p>Đơn hàng của bạn đã được tiếp nhận và đang được xử lý.</p>
                    
                    <div class="order-info">
                        <p><strong>📋 Mã đơn hàng:</strong> #{order_code}</p>
                        <p><strong>📅 Ngày đặt:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        <p><strong>💳 Phương thức thanh toán:</strong> {payment_method_text}</p>
                        <p><strong>📍 Địa chỉ giao hàng:</strong> {shipping_addr.get('street', '')}, {shipping_addr.get('ward', '')}, {shipping_addr.get('district', '')}, {shipping_addr.get('city', '')}</p>
                        <p><strong>👤 Người nhận:</strong> {shipping_addr.get('name', '')} - {shipping_addr.get('phone', '')}</p>
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
                    
                    <p style="margin-top: 30px;">Bạn có thể theo dõi đơn hàng tại đây:</p>
                    <p style="text-align: center;">
                        <a href="https://www.dacsanvietplatform.shop/orders/{order_id}" class="btn">Xem chi tiết đơn hàng</a>
                    </p>
                    
                    <p style="margin-top: 20px;">Mọi thắc mắc vui lòng liên hệ hotline: <strong>1900xxxx</strong> hoặc email: <strong>support@dacsanquetoi.com</strong></p>
                </div>
                <div class="footer">
                    <p>© 2024 Đặc Sản Quê Tôi - Tất cả các quyền được bảo lưu</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await self.email_service.send_email(customer_email, subject, html_content)

    async def _send_shop_order_email(
        self, shop_id: str, order_id: str, order_code: str, 
        order_data: dict, all_items: list
    ):
        """Gửi email thông báo đơn hàng mới cho shop"""
        # Lấy thông tin shop
        shop = await self.shop_collection.find_one({"_id": ObjectId(shop_id)})
        shop_email = shop.get("email") if shop else None
        shop_name = shop.get("name", "Cửa hàng") if shop else "Cửa hàng"
        
        if not shop_email:
            return
        
        # Lọc sản phẩm của shop này
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
                .btn {{ display: inline-block; padding: 10px 20px; background: #ff9800; color: white; text-decoration: none; border-radius: 5px; }}
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
                    <p>Có một đơn hàng mới vừa được đặt từ khách hàng!</p>
                    
                    <div class="order-info">
                        <p><strong>📋 Mã đơn hàng:</strong> #{order_code}</p>
                        <p><strong>📅 Thời gian đặt:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                        <p><strong>👤 Khách hàng:</strong> {shipping_addr.get('name', '')}</p>
                        <p><strong>📞 SĐT khách hàng:</strong> {shipping_addr.get('phone', '')}</p>
                        <p><strong>📍 Địa chỉ giao hàng:</strong> {shipping_addr.get('street', '')}, {shipping_addr.get('ward', '')}, {shipping_addr.get('district', '')}, {shipping_addr.get('city', '')}</p>
                    </div>
                    
                    <h4>Chi tiết sản phẩm trong đơn hàng:</h4>
                    <table>
                        <thead>
                            <tr><th>Sản phẩm</th><th>Số lượng</th><th>Đơn giá</th><th>Thành tiền</th></tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                    </table>
                    
                    <div class="total">
                        <p><strong>Tổng giá trị đơn hàng (shop): {self._format_currency(shop_total)}</strong></p>
                    </div>
                    
                    <p style="margin-top: 30px;">Vui lòng xác nhận và xử lý đơn hàng sớm nhất:</p>
                    <p style="text-align: center;">
                        <a href="https://www.dacsanvietplatform.shop/shop/orders" class="btn">Quản lý đơn hàng</a>
                    </p>
                </div>
                <div class="footer">
                    <p>© 2024 Đặc Sản Quê Tôi - Hệ thống quản lý bán hàng</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await self.email_service.send_email(shop_email, subject, html_content)

    def _format_currency(self, amount: float) -> str:
        """Định dạng tiền tệ"""
        return f"{amount:,.0f}₫".replace(",", ".")

    async def get_user_orders(self, user_id: str):
        """Lấy danh sách đơn hàng của user"""
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
        """Lấy chi tiết đơn hàng"""
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
        """Chuẩn bị response đầy đủ cho order detail"""
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
        """Cập nhật status và gửi notification"""
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": status.value}}
        )
        
        if status == OrderStatus.shipped:
            order = await self.get_order(order_id)
            if order:
                asyncio.create_task(
                    self.notification_service.create_notification(
                        user_id=order["user_id"],
                        type="order",
                        title="Đơn hàng đã giao 🚚",
                        message=f"Đơn hàng #{order_id[-8:].upper()} đã được giao cho đơn vị vận chuyển",
                        reference_id=order_id
                    )
                )
        
        return await self.get_order(order_id)
    
    async def update_payment_status(self, order_id: str, status: str):
        """Cập nhật payment status"""
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"payment_status": status}}
        )
        return await self.get_order(order_id)

    async def cancel_order(self, order_id: str, user_id: str):
        """Hủy đơn hàng với bulk operations"""
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
        
        # Batch restore stock - DÙNG UPDATE_ONE
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
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": OrderStatus.cancelled.value, "cancelled_at": datetime.utcnow()}}
        )
        
        # Update sold quantity in background
        asyncio.create_task(self._update_product_sold_quantity_background(
            order.get("items", []), "decrease"
        ))
        
        return {"status": "success", "message": "Đơn hàng đã được hủy và hoàn kho"}