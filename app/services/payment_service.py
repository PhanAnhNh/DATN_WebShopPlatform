import hashlib
import hmac
import json
import requests 
from datetime import datetime
from bson import ObjectId
from typing import Dict, Any
import urllib.parse

class PaymentService:
    def __init__(self, db):
        self.db = db
        self.payment_collection = db["payments"]
        self.order_collection = db["orders"]
        
        # Cấu hình cổng thanh toán
        self.momo_config = {
            "endpoint": "https://test-payment.momo.vn/v2/gateway/api/create",
            "partner_code": "MOMO",
            "access_key": "YOUR_ACCESS_KEY",
            "secret_key": "YOUR_SECRET_KEY",
            "redirect_url": "http://localhost:5173/payment/return",
            "ipn_url": "http://localhost:8000/api/v1/payments/momo/ipn"
        }
        
        self.vnpay_config = {
            "endpoint": "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
            "tmn_code": "YOUR_TMN_CODE",
            "hash_secret": "YOUR_HASH_SECRET",
            "return_url": "http://localhost:5173/payment/return"
        }

    async def create_payment(self, user_id: str, payment_data: dict):
        """Tạo yêu cầu thanh toán"""
        # Kiểm tra đơn hàng
        order = await self.order_collection.find_one({
            "_id": ObjectId(payment_data["order_id"]),
            "user_id": ObjectId(user_id)
        })
        
        if not order:
            return None, "Không tìm thấy đơn hàng"
        
        # Tạo payment record
        payment = {
            "order_id": ObjectId(payment_data["order_id"]),
            "user_id": ObjectId(user_id),
            "method": payment_data["method"],
            "amount": payment_data["amount"],
            "status": "pending",
            "created_at": datetime.utcnow()
        }
        
        result = await self.payment_collection.insert_one(payment)
        payment_id = str(result.inserted_id)
        
        # Xử lý theo phương thức
        payment_url = None
        if payment_data["method"] == "momo":
            payment_url = await self.create_momo_payment(payment_id, payment_data)
        elif payment_data["method"] == "vnpay":
            payment_url = await self.create_vnpay_payment(payment_id, payment_data)
        elif payment_data["method"] == "zalopay":
            payment_url = await self.create_zalopay_payment(payment_id, payment_data)
        
        return {
            "payment_id": payment_id,
            "payment_url": payment_url,
            "amount": payment_data["amount"],
            "method": payment_data["method"]
        }, None

    async def create_momo_payment(self, payment_id: str, payment_data: dict):
        """Tạo thanh toán MoMo"""
        order_id = payment_data["order_id"]
        amount = str(int(payment_data["amount"]))
        
        # Tạo request ID
        request_id = f"{order_id}_{datetime.now().timestamp()}"
        
        # Tạo chữ ký
        raw_signature = f"accessKey={self.momo_config['access_key']}&amount={amount}&extraData=&ipnUrl={self.momo_config['ipn_url']}&orderId={order_id}&orderInfo=Thanh toan don hang&partnerCode={self.momo_config['partner_code']}&redirectUrl={self.momo_config['redirect_url']}&requestId={request_id}&requestType=captureWallet"
        
        signature = hmac.new(
            bytes(self.momo_config['secret_key'], 'utf-8'),
            bytes(raw_signature, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Gọi API MoMo
        data = {
            "partnerCode": self.momo_config['partner_code'],
            "partnerName": "Test",
            "storeId": "Shop",
            "requestId": request_id,
            "amount": amount,
            "orderId": order_id,
            "orderInfo": "Thanh toan don hang",
            "redirectUrl": self.momo_config['redirect_url'],
            "ipnUrl": self.momo_config['ipn_url'],
            "lang": "vi",
            "extraData": "",
            "requestType": "captureWallet",
            "signature": signature
        }
        
        response = requests.post(self.momo_config['endpoint'], json=data)
        result = response.json()
        
        if result.get("resultCode") == 0:
            return result.get("payUrl")
        
        return None

    async def create_vnpay_payment(self, payment_id: str, payment_data: dict):
        """Tạo thanh toán VNPay"""
        order_id = payment_data["order_id"]
        amount = int(payment_data["amount"]) * 100  # VNPay tính bằng đồng, nhân 100
        
        params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": self.vnpay_config['tmn_code'],
            "vnp_Amount": str(amount),
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": f"{order_id}_{datetime.now().timestamp()}",
            "vnp_OrderInfo": f"Thanh toan don hang {order_id}",
            "vnp_OrderType": "other",
            "vnp_Locale": "vn",
            "vnp_ReturnUrl": self.vnpay_config['return_url'],
            "vnp_IpAddr": "127.0.0.1",
            "vnp_CreateDate": datetime.now().strftime("%Y%m%d%H%M%S")
        }
        
        # Tạo chữ ký
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        hash_data = query_string + "&vnp_SecureHashType=SHA256"
        vnp_secure_hash = hashlib.sha256(
            (hash_data + self.vnpay_config['hash_secret']).encode('utf-8')
        ).hexdigest()
        
        params["vnp_SecureHash"] = vnp_secure_hash
        
        # Tạo URL
        query_string = urllib.parse.urlencode(params)
        payment_url = f"{self.vnpay_config['endpoint']}?{query_string}"
        
        return payment_url

    async def process_momo_ipn(self, data: dict):
        """Xử lý IPN từ MoMo"""
        # Xác thực chữ ký
        raw_signature = f"accessKey={self.momo_config['access_key']}&amount={data['amount']}&extraData={data.get('extraData', '')}&message={data.get('message', '')}&orderId={data['orderId']}&orderInfo={data.get('orderInfo', '')}&orderType={data.get('orderType', '')}&partnerCode={data['partnerCode']}&payType={data.get('payType', '')}&requestId={data['requestId']}&responseTime={data['responseTime']}&resultCode={data['resultCode']}&transId={data['transId']}"
        
        signature = hmac.new(
            bytes(self.momo_config['secret_key'], 'utf-8'),
            bytes(raw_signature, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if signature != data.get('signature'):
            return {"error": "Invalid signature"}
        
        # Cập nhật payment
        if data['resultCode'] == 0:
            await self.payment_collection.update_one(
                {"order_id": ObjectId(data['orderId'])},
                {
                    "$set": {
                        "status": "success",
                        "transaction_id": data['transId'],
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            
            # Cập nhật order
            await self.order_collection.update_one(
                {"_id": ObjectId(data['orderId'])},
                {"$set": {"payment_status": "paid", "status": "paid"}}
            )
        
        return {"status": "ok"}

    async def process_vnpay_return(self, params: dict):
        """Xử lý return từ VNPay"""
        # Xác thực chữ ký
        secure_hash = params.pop('vnp_SecureHash', None)
        
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        hash_data = query_string + "&vnp_SecureHashType=SHA256"
        vnp_secure_hash = hashlib.sha256(
            (hash_data + self.vnpay_config['hash_secret']).encode('utf-8')
        ).hexdigest()
        
        if vnp_secure_hash != secure_hash:
            return {"error": "Invalid signature"}
        
        # Lấy order_id từ vnp_TxnRef
        txn_ref = params.get('vnp_TxnRef', '')
        order_id = txn_ref.split('_')[0]
        
        if params.get('vnp_ResponseCode') == '00':
            # Thanh toán thành công
            await self.payment_collection.update_one(
                {"order_id": ObjectId(order_id)},
                {
                    "$set": {
                        "status": "success",
                        "transaction_id": params.get('vnp_TransactionNo'),
                        "completed_at": datetime.utcnow()
                    }
                }
            )
            
            await self.order_collection.update_one(
                {"_id": ObjectId(order_id)},
                {"$set": {"payment_status": "paid", "status": "paid"}}
            )
            
            return {"success": True, "order_id": order_id}
        
        return {"success": False, "order_id": order_id}
    
    async def process_bank_transfer_webhook(self, data: dict):
        """
        Webhook từ SePay khi có giao dịch vào tài khoản ảo
        """
        try:
            # Xác thực chữ ký (nếu bạn đặt secret trên Sepay)
            # signature = request.headers.get('X-Sepay-Signature')
            # ... (bỏ qua nếu không dùng)

            if data.get('status') != 'success':
                return {"status": "error", "message": "Transaction not successful"}

            virtual_account = data.get('virtualAccount')
            description = data.get('description', '').strip()
            amount = float(data.get('amount', 0))

            # Tìm đơn hàng theo virtual_account (ưu tiên)
            order = None
            if virtual_account:
                order = await self.order_collection.find_one({"virtual_account": virtual_account})
            if not order:
                # fallback: tìm theo order_code trong description
                orders = await self.order_collection.find({"payment_status": {"$ne": "paid"}}).to_list(100)
                for o in orders:
                    if str(o["_id"])[-8:].upper() == description:
                        order = o
                        break

            if not order:
                return {"status": "error", "message": "Order not found"}

            # Kiểm tra số tiền (cho phép sai lệch 1000đ)
            if abs(order["total_amount"] - amount) > 1000:
                return {"status": "error", "message": "Amount mismatch"}

            # Cập nhật thanh toán
            await self.order_collection.update_one(
                {"_id": order["_id"]},
                {"$set": {
                    "payment_status": "paid",
                    "status": "paid",
                    "paid_at": datetime.utcnow(),
                    "payment_transaction_id": data.get("transactionId")
                }}
            )

            # Ghi nhận payment record
            await self.payment_collection.update_one(
                {"order_id": order["_id"], "method": "bank_transfer"},
                {
                    "$set": {
                        "status": "success",
                        "transaction_id": data.get("transactionId"),
                        "completed_at": datetime.utcnow(),
                        "webhook_data": data
                    }
                },
                upsert=True
            )

            # Gửi thông báo cho user
            from app.services.notification_service import NotificationService
            noti_service = NotificationService(self.db)
            await noti_service.create_notification(
                user_id=str(order["user_id"]),
                type="payment",
                title="Thanh toán thành công",
                message=f"Đơn hàng #{str(order['_id'])[-8:].upper()} đã thanh toán qua chuyển khoản",
                reference_id=str(order["_id"])
            )

            return {"status": "success", "order_id": str(order["_id"])}

        except Exception as e:
            print(f"Webhook error: {e}")
            return {"status": "error", "message": str(e)}