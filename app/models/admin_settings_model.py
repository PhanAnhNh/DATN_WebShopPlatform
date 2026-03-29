# app/models/admin_settings_model.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AdminSettings(BaseModel):
    language: str = "vi"  # vi, en
    date_format: str = "dd/mm/yyyy"  # dd/mm/yyyy, mm/dd/yyyy, yyyy-mm-dd
    time_format: str = "24h"  # 24h, 12h
    theme: str = "light"  # light, dark
    timezone: str = "Asia/Ho_Chi_Minh"
    updated_at: datetime = datetime.utcnow()