from pydantic import BaseModel


class ShippingAddress(BaseModel):

    user_id: str
    receiver_name: str
    phone: str
    province: str
    district: str
    ward: str
    address_detail: str
    is_default: bool