# app/models/otp_model.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from enum import Enum

class OTPType(str, Enum):
    forgot_password = "forgot_password"
    verify_email = "verify_email"

class OTPBase(BaseModel):
    email: EmailStr
    otp_code: str
    otp_type: OTPType
    expires_at: datetime
    is_used: bool = False
    created_at: datetime = datetime.utcnow()

class OTPInDB(OTPBase):
    id: str = Field(alias="_id")

class OTPCreate(BaseModel):
    email: EmailStr
    otp_type: OTPType

class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str
    otp_type: OTPType

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str = Field(..., min_length=6)