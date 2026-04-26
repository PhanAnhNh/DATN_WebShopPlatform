import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME

    async def send_email(self, to_email: str, subject: str, html_content: str):
        """Gửi email không block event loop (chạy trong thread pool)"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self._sync_send_email,
            to_email, subject, html_content
        )

    def _sync_send_email(self, to_email: str, subject: str, html_content: str):
        """Phần đồng bộ gửi email (chạy trong thread riêng)"""
        try:
            message = MIMEMultipart()
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            message["Subject"] = subject
            message.attach(MIMEText(html_content, "html"))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(message)
            server.quit()
            print(f"✅ Email sent successfully to {to_email}")
        except Exception as e:
            print(f"❌ Email failed: {e}")

    async def send_forgot_password_email(self, to_email: str, otp_code: str):
        subject = "Đặt lại mật khẩu - Đặc Sản Quê Tôi"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5eee1;
                }}
                .header {{
                    background-color: #2e7d32;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 0 0 8px 8px;
                }}
                .otp-code {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #2e7d32;
                    text-align: center;
                    padding: 20px;
                    background-color: #f0f0f0;
                    border-radius: 8px;
                    letter-spacing: 5px;
                    margin: 20px 0;
                }}
                .warning {{
                    color: #ff6b6b;
                    font-size: 12px;
                    text-align: center;
                    margin-top: 20px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 20px;
                    font-size: 12px;
                    color: #777;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Đặc Sản Quê Tôi</h2>
                </div>
                <div class="content">
                    <h3>Xin chào,</h3>
                    <p>Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.</p>
                    <p>Vui lòng sử dụng mã OTP dưới đây để đặt lại mật khẩu:</p>
                    
                    <div class="otp-code">
                        {otp_code}
                    </div>
                    
                    <p>Mã OTP này có hiệu lực trong vòng <strong>5 phút</strong>.</p>
                    
                    <div class="warning">
                        ⚠️ Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.
                    </div>
                </div>
                <div class="footer">
                    <p>© 2024 Đặc Sản Quê Tôi. Tất cả các quyền được bảo lưu.</p>
                </div>
            </div>
        </body>
        </html>
        """
        await self.send_email(to_email, subject, html_content)