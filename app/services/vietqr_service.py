import httpx
import re
import base64
from typing import Optional

class VietQRService:
    def __init__(self):
        self.api_url = "https://api.vietqr.io/v2/generate"

    async def generate_qr(self, account_number: str, account_name: str, bank_bin: str, amount: int, description: str) -> Optional[bytes]:
        """
        Tạo QR code từ API VietQR.
        Trả về bytes của ảnh PNG.
        """
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
                if data.get("code") == "00":
                    qr_data_url = data["data"]["qrDataURL"]
                    # Loại bỏ prefix data:image/png;base64,
                    base64_str = re.sub(r'^data:image/png;base64,', '', qr_data_url)
                    return base64.b64decode(base64_str)
                else:
                    print(f"VietQR API error: {data}")
                    return None
            except Exception as e:
                print(f"VietQR API exception: {e}")
                return None