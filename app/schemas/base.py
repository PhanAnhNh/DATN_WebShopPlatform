# app/schemas/base.py
from typing import Any, Optional
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from datetime import datetime

# Định nghĩa PyObjectId đúng cách cho Pydantic V2
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema.update(type="string")
        return json_schema

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

class BaseSchema(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )

class ResponseSchema(BaseModel):
    status: str = "success"
    message: str = ""
    data: Any = None

class PaginatedResponse(BaseModel):
    data: list
    total: int
    page: int
    limit: int
    total_pages: int