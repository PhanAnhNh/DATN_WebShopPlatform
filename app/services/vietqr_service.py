import httpx
import re
import base64
from typing import Optional

class VietQRService:
    def __init__(self):
        self.api_url = "https://api.vietqr.io/v2/generate"

    async def generate_qr(self, account_number: str, account_name: str, bank_bin: str, amount: int, description: str) -> Optional[bytes]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "accountNo": account_number,
                "accountName": account_name,
                "acqId": bank_bin,
                "amount": amount,
                "addInfo": description,
                "format": "text"
            }
            try:
                response = await client.post(self.api_url, json=payload)
                data = response.json()
                print("🔍 VietQR API full response:", data)   # <<< in ra log

                if data.get("code") == "00":
                    qr_data_url = data.get("data", {}).get("qrDataURL")
                    if not qr_data_url:
                        print("⚠️ qrDataURL is missing or null")
                        return None
                    base64_str = re.sub(r'^data:image/png;base64,', '', qr_data_url)
                    return base64.b64decode(base64_str)
                else:
                    print(f"❌ VietQR API returned error code: {data.get('code')}, message: {data.get('desc')}")
                    return None
            except Exception as e:
                print(f"⚠️ VietQR exception: {e}")
                return None