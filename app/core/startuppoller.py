# Global poller instance
import asyncio
from venv import logger

import app
from app.db.mongodb import get_database
from app.services.sepay_service import SePayPoller


sepay_poller = None

@app.on_event("startup")
async def startup_event():
    global sepay_poller
    
    # Khởi động SePay poller
    from app.core.config import settings
    
    if settings.SEPAY_API_KEY and settings.SEPAY_API_URL:
        sepay_poller = SePayPoller(
            db=await get_database(),
            api_key=settings.SEPAY_API_KEY,
            api_url=settings.SEPAY_API_URL
        )
        asyncio.create_task(sepay_poller.start_polling(interval_seconds=15))
        logger.info("✅ SePay poller started")
    else:
        logger.warning("⚠️ SePay not configured")

@app.on_event("shutdown")
async def shutdown_event():
    global sepay_poller
    if sepay_poller:
        await sepay_poller.stop()