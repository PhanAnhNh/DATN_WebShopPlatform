# app/models/shop_settings_model.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class GeneralSettings(BaseModel):
    shop_name: str
    shop_email: str
    shop_phone: str
    shop_address: str
    tax_code: Optional[str] = None
    website: Optional[str] = None
    working_hours: str = "8:00 - 22:00"
    timezone: str = "Asia/Ho_Chi_Minh"
    date_format: str = "dd/mm/yyyy"
    currency: str = "VND"
    language: str = "vi"

class NotificationSettings(BaseModel):
    email_notifications: bool = True
    sms_notifications: bool = False
    order_created: bool = True
    order_paid: bool = True
    order_shipped: bool = True
    order_completed: bool = True
    order_cancelled: bool = True
    return_requested: bool = True
    return_processed: bool = True
    low_stock_alert: bool = True
    low_stock_threshold: int = 10
    new_review: bool = True
    new_customer: bool = False
    daily_report: bool = True
    weekly_report: bool = False
    monthly_report: bool = True

class BankAccount(BaseModel):
    id: str
    bank_name: str
    account_number: str
    account_name: str
    branch: str

class MomoInfo(BaseModel):
    phone: str
    name: str

class PaymentSettings(BaseModel):
    cod: bool = True
    bank_transfer: bool = True
    momo: bool = False
    vnpay: bool = False
    zalopay: bool = False
    bank_accounts: List[BankAccount] = []
    momo_info: Optional[MomoInfo] = None
    auto_confirm_payment: bool = True
    payment_timeout: int = 24

class ShippingMethod(BaseModel):
    id: str
    name: str
    fee: float
    days: str

class ShippingSettings(BaseModel):
    free_shipping_threshold: float = 500000
    shipping_fee: float = 30000
    shipping_methods: List[ShippingMethod] = []
    supported_provinces: List[str] = []
    default_province: str = ""
    allow_international: bool = False

class SecuritySettings(BaseModel):
    two_factor_auth: bool = False
    login_attempts: int = 5
    session_timeout: int = 30
    password_expiry: int = 90
    ip_whitelist: List[str] = []
    allow_multiple_sessions: bool = True
    require_strong_password: bool = True

class InvoiceSettings(BaseModel):
    show_logo: bool = True
    show_tax_code: bool = True
    show_phone: bool = True
    show_address: bool = True
    show_bank_info: bool = True
    invoice_prefix: str = "HD"
    invoice_footer: str = "Cảm ơn quý khách đã mua hàng!"
    auto_numbering: bool = True
    next_invoice_number: int = 1001
    print_format: str = "A5"
    email_invoice: bool = True

class SocialSettings(BaseModel):
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None
    whatsapp: Optional[str] = None
    zalo: Optional[str] = None
    show_social_links: bool = True

class SeoSettings(BaseModel):
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    google_analytics: Optional[str] = None
    facebook_pixel: Optional[str] = None
    allow_indexing: bool = True
    sitemap_enabled: bool = True

class ShopSettings(BaseModel):
    shop_id: str
    general: GeneralSettings
    notifications: NotificationSettings
    payment: PaymentSettings
    shipping: ShippingSettings
    security: SecuritySettings
    invoice: InvoiceSettings
    social: SocialSettings
    seo: SeoSettings
    updated_at: datetime = Field(default_factory=datetime.utcnow)