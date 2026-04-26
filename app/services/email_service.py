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
        html_content = f"""... (giữ nguyên như cũ) ..."""
        await self.send_email(to_email, subject, html_content)