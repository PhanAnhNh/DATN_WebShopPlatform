import httpx
import qrcode
from io import BytesIO
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
                print("🔍 VietQR API full response:", data)
                if data.get("code") == "00":
                    qr_code_data = data.get("data", {}).get("qrCode")
                    if not qr_code_data:
                        print("⚠️ qrCode is missing or null")
                        return None
                    # Tạo ảnh QR từ nội dung qrCode (chuẩn EMV)
                    qr = qrcode.QRCode(version=1, box_size=10, border=4)
                    qr.add_data(qr_code_data)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buffer = BytesIO()
                    img.save(buffer, format="PNG")
                    return buffer.getvalue()
                else:
                    print(f"❌ VietQR API error: {data}")
                    return None
            except Exception as e:
                print(f"⚠️ VietQR exception: {e}")
                return None