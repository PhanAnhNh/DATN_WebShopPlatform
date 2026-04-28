# app/services/sepay_poller.py
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId

logger = logging.getLogger(__name__)


class SePayPoller:
    """Poll SePay API for new transactions (fallback when webhook fails)"""
    
    def __init__(self, db, api_key: str, api_url: str):
        self.db = db
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.running = False
        self.last_checked_time = datetime.now() - timedelta(minutes=10)
        # ✅ THÊM DÒNG NÀY - khởi tạo bank_account
        self.bank_account = None  # Sẽ set sau nếu cần
        
    async def start_polling(self, interval_seconds: int = 30):
        """Start polling SePay API for new transactions"""
        self.running = True
        # ✅ BỎ EMOJI - thay bằng text thường
        logger.info(f"[POLLER] SePay poller started - checking every {interval_seconds}s")
        logger.info(f"[POLLER] API URL: {self.api_url}")
        logger.info(f"[POLLER] API Key: {'***' + self.api_key[-8:] if self.api_key else 'NOT SET'}")
        
        while self.running:
            try:
                await self.check_new_transactions()
            except Exception as e:
                logger.error(f"[POLLER] Polling error: {e}")
                import traceback
                traceback.print_exc()
            
            await asyncio.sleep(interval_seconds)
    
    async def check_new_transactions(self):
        """Check for new transactions via SePay API"""
        logger.info("[POLLER] Checking for new transactions...")
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Lấy giao dịch từ lần check cuối
            from_timestamp = int(self.last_checked_time.timestamp())
            to_timestamp = int(datetime.now().timestamp())
            
            # ✅ THỬ NHIỀU ENDPOINT
            endpoints = [
                f"{self.api_url}/transactions",
                f"{self.api_url}/user-transactions",
            ]
            
            for url in endpoints:
                try:
                    params = {
                        "page": 1,
                        "limit": 20,
                        "from_date": from_timestamp,
                        "to_date": to_timestamp
                    }
                    
                    logger.info(f"[POLLER] Trying endpoint: {url}")
                    
                    async with session.get(url, headers=headers, params=params) as resp:
                        logger.info(f"[POLLER] Response status: {resp.status}")
                        
                        if resp.status == 200:
                            data = await resp.json()
                            logger.info(f"[POLLER] Response type: {type(data)}")
                            
                            # Lấy danh sách transactions
                            transactions = []
                            if isinstance(data, dict):
                                transactions = data.get("transactions", data.get("data", []))
                            elif isinstance(data, list):
                                transactions = data
                            
                            logger.info(f"[POLLER] Found {len(transactions)} transactions")
                            
                            for tx in transactions:
                                await self.process_transaction(tx)
                            
                            # Nếu có transactions thì không cần thử endpoint khác
                            if transactions:
                                break
                                
                        elif resp.status == 404:
                            logger.warning(f"[POLLER] Endpoint not found: {url}")
                        elif resp.status == 401:
                            logger.error("[POLLER] Authentication failed - check API key")
                            return
                            
                except Exception as e:
                    logger.error(f"[POLLER] Error with {url}: {e}")
            
            # Cập nhật thời gian check cuối
            self.last_checked_time = datetime.now()
    
    async def process_transaction(self, tx: dict):
        """Process a single transaction"""
        try:
            tx_amount = float(tx.get("amount_in", 0))
            tx_description = tx.get("description", "").strip()
            tx_id = str(tx.get("id"))
            
            if tx_amount <= 0:
                return
            
            logger.info(f"[POLLER] Processing transaction: id={tx_id}, amount={tx_amount}, desc='{tx_description}'")
            
            # Tìm order_code trong description (loại bỏ prefix SEVQR nếu có)
            import re
            # Loại bỏ prefix SEVQR
            clean_desc = re.sub(r'^SEVQR\s+', '', tx_description, flags=re.IGNORECASE).strip()
            # Tìm 8 ký tự cuối (order_code)
            order_code = clean_desc.upper()
            
            logger.info(f"[POLLER] Extracted order_code: {order_code}")
            
            # Tìm order
            order = await self.db["orders"].find_one({
                "$or": [
                    {"order_code": order_code},
                    {"order_code": {"$regex": f".*{order_code}", "$options": "i"}}
                ],
                "payment_status": {"$ne": "paid"}
            })
            
            if not order:
                # Thử tìm theo _id (fallback)
                try:
                    if len(order_code) == 24:
                        order = await self.db["orders"].find_one({
                            "_id": ObjectId(order_code),
                            "payment_status": {"$ne": "paid"}
                        })
                except:
                    pass
            
            if order:
                logger.info(f"[POLLER] Found order: {order_code}, amount: {order.get('total_amount')}")
                
                if tx_amount >= order.get("total_amount", 0):
                    from app.services.sepay_service import SePayService
                    sepay_service = SePayService(self.db)
                    await sepay_service._process_successful_payment(
                        order, tx_id, tx_amount, tx
                    )
                    logger.info(f"[POLLER] Payment processed for order {order_code}")
                else:
                    logger.warning(f"[POLLER] Amount mismatch: {tx_amount} < {order.get('total_amount')}")
            else:
                logger.warning(f"[POLLER] No order found for code: {order_code}")
                
        except Exception as e:
            logger.error(f"[POLLER] Error processing transaction: {e}")
    
    async def stop(self):
        """Stop the poller"""
        self.running = False
        logger.info("[POLLER] SePay poller stopped")