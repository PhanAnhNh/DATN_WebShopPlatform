# app/services/sepay_poller.py
import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Optional
from bson import ObjectId

logger = logging.getLogger(__name__)


class SePayPoller:
    """Poll SePay API for new transactions (fallback when webhook fails)"""
    
    def __init__(self, db, api_key: str, api_url: str):
        self.db = db
        self.api_key = api_key
        self.api_url = api_url
        self.running = False
        self.last_checked_transaction_id = None
        
    async def start_polling(self, interval_seconds: int = 30):
        """Start polling SePay API for new transactions"""
        self.running = True
        logger.info(f"🔄 SePay poller started - checking every {interval_seconds}s")
        
        while self.running:
            try:
                await self.check_new_transactions()
            except Exception as e:
                logger.error(f"Polling error: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    async def check_new_transactions(self):
        """Check for new transactions via SePay API"""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Tìm giao dịch mới trong 5 phút qua
            params = {
                "page": 1,
                "limit": 20,
                "from_date": datetime.now().timestamp() - 300  # 5 minutes ago
            }
            
            try:
                async with session.get(
                    f"{self.api_url}/transactions",
                    headers=headers,
                    params=params
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        transactions = data.get("transactions", [])
                        
                        # Lọc giao dịch mới (chưa xử lý)
                        for tx in transactions:
                            tx_amount = float(tx.get("amount_in", 0))
                            tx_description = tx.get("description", "").strip()
                            tx_id = str(tx.get("id"))
                            
                            # Bỏ qua giao dịch đã xử lý
                            if self.last_checked_transaction_id == tx_id:
                                continue
                            
                            # Tìm order theo description (order_code)
                            order = await self.db["orders"].find_one({
                                "order_code": tx_description,
                                "payment_status": {"$ne": "paid"}
                            })
                            
                            if order and tx_amount >= order.get("total_amount", 0):
                                # Xử lý thanh toán thành công
                                from app.services.sepay_service import SePayService
                                sepay_service = SePayService(self.db)
                                await sepay_service._process_successful_payment(
                                    order, tx_id, tx_amount, tx
                                )
                                logger.info(f"✅ Poller processed payment for order {tx_description}")
                            
                            self.last_checked_transaction_id = tx_id
                    
            except Exception as e:
                logger.error(f"Error fetching transactions: {e}")
    
    async def stop(self):
        """Stop the poller"""
        self.running = False
        logger.info("🛑 SePay poller stopped")