# app/services/traceability_service.py
from bson import ObjectId
from datetime import datetime
from typing import List, Optional
import json

class TraceabilityService:
    def __init__(self, db):
        self.db = db
        self.collection = db["product_traceability"]
    
    async def create_traceability(self, product_id: str, trace_data: dict):
        """Tạo traceability cho sản phẩm"""
        trace_doc = {
            "product_id": ObjectId(product_id),
            "trace_events": trace_data.get("trace_events", []),
            "qr_code_data": f"/product/{product_id}/trace",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.collection.insert_one(trace_doc)
        
        # Cập nhật product
        await self.db["products"].update_one(
            {"_id": ObjectId(product_id)},
            {"$set": {
                "has_traceability": True,
                "traceability_id": str(result.inserted_id)
            }}
        )
        
        trace_doc["_id"] = str(result.inserted_id)
        trace_doc["product_id"] = str(trace_doc["product_id"])
        
        return trace_doc
    
    async def get_traceability_by_product(self, product_id: str):
        """Lấy traceability theo product_id"""
        trace = await self.collection.find_one({"product_id": ObjectId(product_id)})
        if trace:
            trace["_id"] = str(trace["_id"])
            trace["product_id"] = str(trace["product_id"])
        return trace
    
    async def add_trace_event(self, product_id: str, event: dict):
        """Thêm event vào traceability"""
        result = await self.collection.update_one(
            {"product_id": ObjectId(product_id)},
            {
                "$push": {"trace_events": event},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0
    
    async def update_trace_event(self, product_id: str, event_index: int, event: dict):
        """Cập nhật event"""
        trace = await self.get_traceability_by_product(product_id)
        if not trace:
            return None
        
        trace_events = trace.get("trace_events", [])
        if event_index >= len(trace_events):
            return None
        
        trace_events[event_index] = event
        
        result = await self.collection.update_one(
            {"product_id": ObjectId(product_id)},
            {
                "$set": {
                    "trace_events": trace_events,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    async def delete_trace_event(self, product_id: str, event_index: int):
        """Xóa event"""
        result = await self.collection.update_one(
            {"product_id": ObjectId(product_id)},
            {
                "$pull": {"trace_events": {"$eq": event_index}},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        return result.modified_count > 0