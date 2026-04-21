# app/core/r2_config.py
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class R2Config:
    # Lấy từ Cloudflare
    ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
    ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "anh-web-san-pham")
    
    # Endpoint URL
    ENDPOINT_URL = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
    
    # Public URL (sau khi bật Public Access)
    PUBLIC_URL_BASE = "https://pub-b7a5a6741ffb4fd58f69c8187743adba.r2.dev"

# Debug: In ra để kiểm tra (sau khi fix sẽ xóa)
print(f"=== R2 Config Debug ===")
print(f"ACCOUNT_ID: {R2Config.ACCOUNT_ID}")
print(f"ACCESS_KEY_ID: {R2Config.ACCESS_KEY_ID[:10] if R2Config.ACCESS_KEY_ID else 'None'}...")
print(f"BUCKET_NAME: {R2Config.BUCKET_NAME}")
print(f"ENDPOINT_URL: {R2Config.ENDPOINT_URL}")
print(f"PUBLIC_URL_BASE: {R2Config.PUBLIC_URL_BASE}")
print(f"======================")