# app/services/location_service.py
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime
import math
from app.db.mongodb import get_database
from app.models.location_model import Location, Province, District
from app.schemas.locations import LocationCreate, LocationUpdate, ProvinceCreate, ProvinceUpdate

class LocationService:
    def __init__(self):
        self.db = None
    
    async def _get_collections(self):
        if self.db is None:
            self.db = get_database()
        return self.db["locations"], self.db["provinces"], self.db["districts"]

    # ========== Location Management ==========
    
    async def create_location(self, location_data: LocationCreate, user_id: str = None) -> Dict[str, Any]:
        locations_col, _, _ = await self._get_collections()
        
        location_dict = location_data.model_dump()
        location_dict["created_by"] = user_id
        location_dict["created_at"] = datetime.utcnow()
        location_dict["updated_at"] = datetime.utcnow()
        location_dict["status"] = "active"
        
        result = await locations_col.insert_one(location_dict)
        
        location_dict["_id"] = str(result.inserted_id)
        return location_dict
    
    async def get_location(self, location_id: str) -> Optional[Dict[str, Any]]:
        locations_col, _, _ = await self._get_collections()
        
        location = await locations_col.find_one({"_id": ObjectId(location_id)})
        if location:
            location["_id"] = str(location["_id"])
        return location

    async def get_locations_by_province(self, province_id: str, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        locations_col, _, _ = await self._get_collections()
        
        skip = (page - 1) * limit
        
        # QUAN TRỌNG: province_id trong database có thể là string, không phải ObjectId
        # Nên query trực tiếp với string
        query = {"province_id": province_id, "status": "active"}
        
        # Debug
        print(f"Query locations with province_id: {province_id}")
        
        cursor = locations_col.find(query)
        total = await locations_col.count_documents(query)
        
        locations = []
        async for doc in cursor.limit(limit).skip(skip):
            doc["_id"] = str(doc["_id"])
            locations.append(doc)
        
        return {
            "data": locations,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0
        }
    
    async def get_nearby_locations(self, lat: float, lng: float, radius_km: float = 10, 
                                     category: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        locations_col, _, _ = await self._get_collections()
        
        # Tính toán bounding box để tối ưu
        lat_delta = radius_km / 111.0  # 1 độ ~ 111km
        lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
        
        query = {
            "lat": {"$gte": lat - lat_delta, "$lte": lat + lat_delta},
            "lng": {"$gte": lng - lng_delta, "$lte": lng + lng_delta},
            "status": "active"
        }
        
        if category:
            query["category"] = category
        
        locations = []
        async for doc in locations_col.find(query).limit(limit):
            # Tính khoảng cách thực tế
            doc["_id"] = str(doc["_id"])
            doc["distance_km"] = self._calculate_distance(lat, lng, doc["lat"], doc["lng"])
            locations.append(doc)
        
        # Sắp xếp theo khoảng cách
        locations.sort(key=lambda x: x["distance_km"])
        
        return locations
    
    async def update_location(self, location_id: str, update_data: LocationUpdate) -> Optional[Dict[str, Any]]:
        locations_col, _, _ = await self._get_collections()
        
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await locations_col.update_one(
            {"_id": ObjectId(location_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count:
            return await self.get_location(location_id)
        return None
    
    async def delete_location(self, location_id: str, soft_delete: bool = True) -> bool:
        locations_col, _, _ = await self._get_collections()
        
        if soft_delete:
            result = await locations_col.update_one(
                {"_id": ObjectId(location_id)},
                {"$set": {"status": "inactive", "updated_at": datetime.utcnow()}}
            )
        else:
            result = await locations_col.delete_one({"_id": ObjectId(location_id)})
        
        return result.modified_count > 0 or result.deleted_count > 0
    
    # ========== Province Management ==========
    
    async def create_province(self, province_data: ProvinceCreate) -> Dict[str, Any]:
        _, provinces_col, _ = await self._get_collections()
        
        province_dict = province_data.model_dump()
        province_dict["created_at"] = datetime.utcnow()
        province_dict["updated_at"] = datetime.utcnow()
        province_dict["status"] = "active"
        
        result = await provinces_col.insert_one(province_dict)
        
        province_dict["_id"] = str(result.inserted_id)
        return province_dict
    
    async def get_province(self, province_id: str) -> Optional[Dict[str, Any]]:
        _, provinces_col, _ = await self._get_collections()
        
        province = await provinces_col.find_one({"_id": ObjectId(province_id)})
        if province:
            province["_id"] = str(province["_id"])
        return province
    
    async def get_all_provinces(self, status: str = "active") -> List[Dict[str, Any]]:
        _, provinces_col, _ = await self._get_collections()
        
        query = {"status": status} if status else {}
        
        provinces = []
        async for doc in provinces_col.find(query).sort("name", 1):
            doc["_id"] = str(doc["_id"])
            provinces.append(doc)
        
        return provinces
    
    async def update_province(self, province_id: str, update_data: ProvinceUpdate) -> Optional[Dict[str, Any]]:
        _, provinces_col, _ = await self._get_collections()
        
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await provinces_col.update_one(
            {"_id": ObjectId(province_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count:
            return await self.get_province(province_id)
        return None
    
    async def delete_province(self, province_id: str, soft_delete: bool = True) -> bool:
        _, provinces_col, _ = await self._get_collections()
        
        if soft_delete:
            result = await provinces_col.update_one(
                {"_id": ObjectId(province_id)},
                {"$set": {"status": "inactive", "updated_at": datetime.utcnow()}}
            )
        else:
            result = await provinces_col.delete_one({"_id": ObjectId(province_id)})
        
        return result.modified_count > 0 or result.deleted_count > 0
    
    async def get_province_statistics(self, province_id: str) -> Dict[str, Any]:
        locations_col, _, _ = await self._get_collections()
        
        total_locations = await locations_col.count_documents({
            "province_id": province_id,
            "status": "active"
        })
        
        # Thống kê theo category
        pipeline = [
            {"$match": {"province_id": province_id, "status": "active"}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}}
        ]
        
        category_stats = []
        async for doc in locations_col.aggregate(pipeline):
            category_stats.append({"category": doc["_id"], "count": doc["count"]})
        
        return {
            "province_id": province_id,
            "total_locations": total_locations,
            "category_stats": category_stats
        }
    
    # ========== Helper Methods ==========
    
    @staticmethod
    def _calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Tính khoảng cách giữa 2 điểm (km) sử dụng công thức Haversine"""
        R = 6371  # Bán kính trái đất (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * \
            math.sin(delta_lng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return round(R * c, 2)

location_service = LocationService()