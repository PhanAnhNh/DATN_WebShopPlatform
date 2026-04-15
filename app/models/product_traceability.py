# app/models/product_traceability.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class TraceStage(str, Enum):
    CULTIVATION = "cultivation"  # Nuôi trồng
    PRODUCTION = "production"    # Sản xuất
    PROCESSING = "processing"    # Chế biến
    TRANSPORTATION = "transportation"  # Vận chuyển
    DISTRIBUTION = "distribution"      # Phân phối
    CERTIFICATION = "certification"    # Chứng nhận

class TraceEvent(BaseModel):
    stage: TraceStage
    title: str
    description: str
    location: Optional[str] = None
    date: datetime
    images: List[str] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    responsible_party: Optional[str] = None
    metadata: dict = Field(default_factory=dict)

class ProductTraceability(BaseModel):
    product_id: str
    trace_events: List[TraceEvent] = Field(default_factory=list)
    qr_code_data: str
    created_at: datetime
    updated_at: datetime

class TraceabilityCreate(BaseModel):
    trace_events: List[TraceEvent] = Field(default_factory=list)

class TraceabilityResponse(ProductTraceability):
    id: str = Field(alias="_id")
    
    class Config:
        populate_by_name = True