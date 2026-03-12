from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CategoryBase(BaseModel):

    name: str = Field(..., min_length=2, max_length=100)

    parent_id: Optional[str] = None

    icon_url: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):

    name: Optional[str] = None
    parent_id: Optional[str] = None
    icon_url: Optional[str] = None


class CategoryResponse(CategoryBase):

    id: str = Field(alias="_id")

    created_at: datetime

    class Config:
        populate_by_name = True