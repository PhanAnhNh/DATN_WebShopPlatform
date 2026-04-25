from bson import ObjectId
from datetime import datetime
from app.models.orders_model import OrderStatus
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.shipping_unit_service import ShippingUnitService


class OrderService:

    def __init__(self, db):
        self.db = db
        self.collection = db["orders"]
        self.product_collection = db["products"]
        self.shop_collection = db["shops"]
        self.cart_collection = db["carts"]
        self.variant_collection = db["product_variants"]
        self.user_collection = db["users"]  # Thêm để lấy thông tin user
        self.notification_service = NotificationService(db)
        self.shipping_unit_service = ShippingUnitService(db)
        self.email_service = EmailService()  # Thêm email service

    async def create_order(self, user_id: str, order_data: dict):
        total_price = 0
        items_to_save = []
        
        # Lấy thông tin người đặt hàng
        customer = await self.user_collection.find_one({"_id": ObjectId(user_id)})
        customer_email = customer.get("email") if customer else None
        customer_name = customer.get("full_name") or customer.get("username", "Khách hàng")
        
        # Validate each item và lấy thông tin shop
        shop_ids = set()
        for item in order_data["items"]:
            shop_ids.add(item["shop_id"])
            if item.get("variant_id"):
                variant = await self.variant_collection.find_one({"_id": ObjectId(item["variant_id"])})
                if not variant or variant["stock"] < item["quantity"]:
                    raise Exception(f"Sản phẩm {item.get('variant_name')} không đủ hàng")
                
                price = variant["price"]
                await self.variant_collection.update_one(
                    {"_id": variant["_id"]}, 
                    {"$inc": {"stock": -item["quantity"]}}
                )
            else:
                product = await self.product_collection.find_one({"_id": ObjectId(item["product_id"])})
                if not product or product.get("stock", 0) < item["quantity"]:
                    raise Exception("Sản phẩm không đủ hàng")
                
                price = product.get("price", 0)
                await self.product_collection.update_one(
                    {"_id": product["_id"]}, 
                    {"$inc": {"stock": -item["quantity"]}}
                )
            
            total_price += price * item["quantity"]
            items_to_save.append({
                "product_id": ObjectId(item["product_id"]),
                "variant_id": ObjectId(item["variant_id"]) if item.get("variant_id") else None,
                "shop_id": ObjectId(item["shop_id"]),
                "quantity": item["quantity"],
                "price": price,
                "variant_name": item.get("variant_name", "")
            })
        
        # Format shipping address
        shipping_addr = order_data["shipping_address"]
        formatted_address = shipping_addr.get("full_address") or f"{shipping_addr['street']}, {shipping_addr['ward']}, {shipping_addr['district']}, {shipping_addr['city']}, {shipping_addr['country']}"
        
        # Lấy thông tin shipping unit nếu có
        shipping_unit_info = None
        if order_data.get("shipping_unit_id"):
            shipping_unit = await self.shipping_unit_service.get_shipping_unit_by_id(
                order_data["shipping_unit_id"],
                None
            )
            if shipping_unit:
                shipping_unit_info = {
                    "id": shipping_unit["id"],
                    "name": shipping_unit["name"],
                    "code": shipping_unit["code"],
                    "shipping_fee": order_data["shipping_fee"],
                    "estimated_delivery_days": shipping_unit["estimated_delivery_days"]
                }
        
        # Create order
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
        
        # Thêm shipping unit info nếu có
        if shipping_unit_info:
            order["shipping_unit"] = shipping_unit_info
            order["shipping_unit_id"] = ObjectId(order_data["shipping_unit_id"])
        
        # Add voucher if present
        if order_data.get("voucher"):
            order["voucher"] = {
                "id": ObjectId(order_data["voucher"]["id"]),
                "code": order_data["voucher"]["code"],
                "discount": order_data["voucher"]["discount"]
            }
        
        result = await self.collection.insert_one(order)
        
        # Clear cart
        await self.cart_collection.delete_one({"user_id": ObjectId(user_id)})
        
        order_id = str(result.inserted_id)
        order_code = order_id[-8:].upper()
        
        # ========== TẠO THÔNG BÁO ==========
        # 1. Thông báo cho người đặt hàng
        await self.notification_service.create_notification(
            user_id=user_id,
            type="order",
            title="Đặt hàng thành công",
            message=f"Đơn hàng #{order_code} đã được đặt thành công",
            reference_id=order_id
        )
        
        # 2. Thông báo cho các shop
        for shop_id in shop_ids:
            await self.notification_service.create_notification(
                user_id=shop_id,
                type="order",
                title="Đơn hàng mới",
                message=f"Có đơn hàng mới #{order_code} cần xử lý",
                reference_id=order_id
            )
        
        # ========== GỬI EMAIL XÁC NHẬN ==========
        # 1. Gửi email cho khách hàng
        if customer_email:
            await self._send_customer_order_email(customer_email, customer_name, order_id, order_code, order_data)
        
        # 2. Gửi email cho các shop
        for shop_id in shop_ids:
            await self._send_shop_order_email(shop_id, order_id, order_code, order_data)
        
        # Convert ObjectId to string before returning
        order["_id"] = order_id
        order["user_id"] = str(order["user_id"])
        if order.get("voucher") and order["voucher"].get("id"):
            order["voucher"]["id"] = str(order["voucher"]["id"])
        if order.get("shipping_unit_id"):
            order["shipping_unit_id"] = str(order["shipping_unit_id"])
        
        for item in order["items"]:
            item["product_id"] = str(item["product_id"])
            item["shop_id"] = str(item["shop_id"])
            if item.get("variant_id"):
                item["variant_id"] = str(item["variant_id"])
        await self._update_product_sold_quantity(items_to_save, operation="increase")

        return order

    async def _send_customer_order_email(self, customer_email: str, customer_name: str, order_id: str, order_code: str, order_data: dict):
        """Gửi email xác nhận đơn hàng cho khách hàng"""
        subject = f"Xác nhận đơn hàng #{order_code} - Đặc Sản Quê Tôi"
        
        # Tạo danh sách sản phẩm trong email
        items_html = ""
        for item in order_data["items"]:
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
                        <p><strong>📍 Địa chỉ giao hàng:</strong> {order_data['shipping_address']['street']}, {order_data['shipping_address']['ward']}, {order_data['shipping_address']['district']}, {order_data['shipping_address']['city']}</p>
                        <p><strong>👤 Người nhận:</strong> {order_data['shipping_address']['name']} - {order_data['shipping_address']['phone']}</p>
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
                    
                    <p style="margin-top: 20px;">Mọi thắc mắc vui lòng liên hệ hotline: <strong>1900xxxx</strong> hoặc email: <strong>support@dacsanqueto i.com</strong></p>
                </div>
                <div class="footer">
                    <p>© 2024 Đặc Sản Quê Tôi - Tất cả các quyền được bảo lưu</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        await self.email_service.send_email(customer_email, subject, html_content)

    async def _send_shop_order_email(self, shop_id: str, order_id: str, order_code: str, order_data: dict):
        """Gửi email thông báo đơn hàng mới cho shop"""
        # Lấy thông tin shop
        shop = await self.shop_collection.find_one({"_id": ObjectId(shop_id)})
        shop_email = shop.get("email") if shop else None
        shop_name = shop.get("name", "Cửa hàng") if shop else "Cửa hàng"
        
        if not shop_email:
            return
        
        # Lọc sản phẩm của shop này
        shop_items = [item for item in order_data["items"] if item["shop_id"] == shop_id]
        
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
                        <p><strong>👤 Khách hàng:</strong> {order_data['shipping_address']['name']}</p>
                        <p><strong>📞 SĐT khách hàng:</strong> {order_data['shipping_address']['phone']}</p>
                        <p><strong>📍 Địa chỉ giao hàng:</strong> {order_data['shipping_address']['street']}, {order_data['shipping_address']['ward']}, {order_data['shipping_address']['district']}, {order_data['shipping_address']['city']}</p>
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
        cursor = self.collection.find({
            "user_id": ObjectId(user_id)
        }).sort("created_at", -1)

        orders = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["user_id"] = str(doc["user_id"])

            for item in doc.get("items", []):
                item["product_id"] = str(item["product_id"])
                item["shop_id"] = str(item["shop_id"])
                if item.get("variant_id"):
                    item["variant_id"] = str(item["variant_id"])

            orders.append(doc)

        return orders

    async def get_order(self, order_id: str):
        try:
            order = await self.collection.find_one({
                "_id": ObjectId(order_id)
            })
        except:
            return None

        if not order:
            return None

        # Tạo dict mới để tránh lỗi ObjectId
        result = {
            "_id": str(order["_id"]),
            "user_id": str(order["user_id"]),
            "total_amount": order.get("total_amount", 0),
            "total_price": order.get("total_amount", 0),
            "subtotal": order.get("subtotal", 0),
            "discount": order.get("discount", 0),
            "shipping_fee": order.get("shipping_fee", 0),
            "status": order.get("status", "pending"),
            "payment_status": order.get("payment_status", "unpaid"),
            "payment_method": order.get("payment_method", "cod"),
            "shipping_address": order.get("shipping_address", ""),
            "shipping_address_details": order.get("shipping_address_details", {}),
            "note": order.get("note", ""),
            "created_at": order.get("created_at")
        }
        
        # Xử lý items
        items = []
        for idx, item in enumerate(order.get("items", [])):
            items.append({
                "_id": f"{result['_id']}_item_{idx}",
                "product_id": str(item.get("product_id")),
                "shop_id": str(item.get("shop_id")),
                "quantity": item.get("quantity", 0),
                "price": item.get("price", 0),
                "variant_id": str(item.get("variant_id")) if item.get("variant_id") else None,
                "variant_name": item.get("variant_name", "")
            })
        
        result["items"] = items
        
        # Xử lý voucher
        if order.get("voucher"):
            voucher = order["voucher"]
            result["voucher"] = {
                "id": str(voucher.get("id")) if voucher.get("id") else None,
                "code": voucher.get("code", ""),
                "discount": voucher.get("discount", 0)
            }
        
        # Xử lý shipping unit
        if order.get("shipping_unit"):
            result["shipping_unit"] = order.get("shipping_unit")
        
        if order.get("shipping_unit_id"):
            result["shipping_unit_id"] = str(order["shipping_unit_id"])
        
        return result

    async def update_order_status(self, order_id: str, status: OrderStatus):
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": status.value}}
        )
        
        # Nếu chuyển sang trạng thái shipped, có thể gửi thông báo
        if status == OrderStatus.shipped:
            order = await self.get_order(order_id)
            if order:
                # Thông báo cho khách hàng
                await self.notification_service.create_notification(
                    user_id=order["user_id"],
                    type="order",
                    title="Đơn hàng đã giao",
                    message=f"Đơn hàng #{order_id[-8:].upper()} đã được giao cho đơn vị vận chuyển",
                    reference_id=order_id
                )
        
        return await self.get_order(order_id)
    
    async def update_payment_status(self, order_id: str, status: str):
        """Cập nhật khi khách đã trả tiền (gọi từ Webhook hoặc Admin)"""
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"payment_status": status}}
        )
        return await self.get_order(order_id)

    async def _update_product_sold_quantity(self, items: list, operation: str = "increase"):
        """
        Cập nhật sold_quantity cho sản phẩm.
        operation: "increase" (khi đặt hàng) hoặc "decrease" (khi hủy hàng)
        """
        for item in items:
            product_id = item["product_id"]
            quantity = item["quantity"]
            change = quantity if operation == "increase" else -quantity

            # Cập nhật sold_quantity cho sản phẩm chính
            await self.db["products"].update_one(
                {"_id": ObjectId(product_id)},
                {"$inc": {"sold_quantity": change}}
            )

            # Nếu có variant, cũng cập nhật sold_quantity cho variant (tùy chọn, nếu muốn theo dõi chi tiết)
            if item.get("variant_id"):
                await self.db["product_variants"].update_one(
                    {"_id": ObjectId(item["variant_id"])},
                    {"$inc": {"sold_quantity": change}}  # Nhớ thêm trường này trong model variant nếu cần
                )
            print(f"✅ Updated sold_quantity for product {product_id}: {change}")

    async def cancel_order(self, order_id: str, user_id: str):
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

        # 1. Hoàn lại kho (Stock)
        for item in order.get("items", []):
            if item.get("variant_id"):
                await self.db["product_variants"].update_one(
                    {"_id": ObjectId(item["variant_id"])},
                    {"$inc": {"stock": item["quantity"]}}
                )
            else:
                await self.db["products"].update_one(
                    {"_id": ObjectId(item["product_id"])},
                    {"$inc": {"stock": item["quantity"]}}
                )
            
            # 2. Trừ lại doanh thu dự kiến của Shop
            await self.shop_collection.update_one(
                {"_id": ObjectId(item["shop_id"])},
                {"$inc": {
                    "total_revenue": -(item["price"] * item["quantity"]),
                    "total_orders": -1
                }}
            )

        # 3. Cập nhật trạng thái đơn hàng
        await self.collection.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {"status": OrderStatus.cancelled.value, "cancelled_at": datetime.utcnow()}}
        )
        await self._update_product_sold_quantity(order.get("items", []), operation="decrease")

        return {"status": "success", "message": "Đơn hàng đã được hủy và hoàn kho"}