# app/models/favorite_model.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class FavoriteBase(BaseModel):
    user_id: str
    product_id: str

class FavoriteCreate(FavoriteBase):
    pass

class FavoriteResponse(FavoriteBase):
    id: str = Field(alias="_id")
    created_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True