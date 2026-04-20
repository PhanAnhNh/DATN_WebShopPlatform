# app/models/shops_model.py

from pydantic import BaseModel, EmailStr, Field, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from typing import Optional, Any
from datetime import date, datetime
from bson import ObjectId

# ✅ Định nghĩa PyObjectId ĐÚNG cho Pydantic V2
class PyObjectId(str):
    """Class để xử lý ObjectId trong Pydantic V2"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(str)
        )
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return {"type": "string"}

class ShopBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str = Field(..., min_length=3)
    slug: str = Field(..., description="URL thân thiện")
    description: Optional[str] = None

    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None

    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    location_id: Optional[str] = Field(None, description="ID của location trong bảng locations")  # ✅ Đổi thành str

class ShopCreate(ShopBase):
    pass

class ShopWithOwnerCreate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Thông tin shop
    shop_name: str = Field(..., min_length=3)
    shop_slug: str = Field(..., description="URL thân thiện")
    shop_description: Optional[str] = None
    shop_phone: Optional[str] = None
    shop_email: Optional[str] = None
    shop_address: Optional[str] = None
    shop_province: Optional[str] = None
    shop_district: Optional[str] = None
    shop_ward: Optional[str] = None
    shop_logo_url: Optional[str] = None
    shop_banner_url: Optional[str] = None
    location_id: Optional[str] = Field(None, description="ID của location trong bảng locations")
    
    # Thông tin chủ shop
    owner_username: str = Field(..., min_length=3)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=6)
    owner_full_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_gender: Optional[str] = None
    owner_dob: Optional[date] = None
    owner_address: Optional[str] = None

class ShopUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    status: Optional[str] = None
    location_id: Optional[str] = Field(None, description="ID của location trong bảng locations")

class ShopInDB(ShopBase):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: str = Field(alias="_id")
    owner_id: str  # ✅ Đổi thành str

    status: str = "active"
    is_verified: bool = False

    products_count: int = 0
    posts_count: int = 0
    followers_count: int = 0
    total_orders: int = 0
    total_revenue: float = 0
    view_count: int = 0

    created_at: datetime
    updated_at: datetime

class ShopBankInfo(BaseModel):
    """Thông tin ngân hàng của shop"""
    bank_name: str = Field(..., description="Tên ngân hàng")
    bank_code: str = Field(..., description="Mã ngân hàng (BIDV, VCB, etc)")
    account_number: str = Field(..., description="Số tài khoản")
    account_name: str = Field(..., description="Chủ tài khoản")
    branch: Optional[str] = Field(None, description="Chi nhánh")
    qr_code_url: Optional[str] = Field(None, description="URL QR code thanh toán")

class ShopPaymentSettings(BaseModel):
    """Cài đặt thanh toán của shop"""
    bank_info: Optional[ShopBankInfo] = None
    enable_bank_transfer: bool = True