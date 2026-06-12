# app/services/distance_service.py
import httpx
from typing import Optional, Dict
import json
import math
from app.core.config import settings

class DistanceService:
    def __init__(self):
        self.access_token = settings.MAPBOX_ACCESS_TOKEN
        if not self.access_token:
            print("⚠️ Warning: MAPBOX_ACCESS_TOKEN not found in environment")
        self.base_url = "https://api.mapbox.com/directions/v5/mapbox/driving"
    
    async def get_road_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> Optional[Dict]:
        """
        Sử dụng Mapbox Directions API để tính khoảng cách đường đi thực tế
        """
        try:
            # Mapbox yêu cầu định dạng: lng,lat
            coordinates = f"{lng1},{lat1};{lng2},{lat2}"
            url = f"{self.base_url}/{coordinates}"
            
            params = {
                "access_token": self.access_token,
                "geometries": "geojson",
                "overview": "simplified",
                "steps": "false",
                "alternatives": "false"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('code') == 'Ok' and data.get('routes'):
                        route = data['routes'][0]
                        distance_km = route['distance'] / 1000  # Chuyển từ mét sang km
                        duration_min = route['duration'] / 60   # Chuyển từ giây sang phút
                        
                        print(f"✅ Mapbox: {distance_km:.2f} km, {duration_min:.1f} mins")
                        return {
                            "distance_km": round(distance_km, 2),
                            "duration_min": round(duration_min, 1)
                        }
                    else:
                        print(f"⚠️ Mapbox error: {data.get('code')}")
                        return None
                else:
                    print(f"❌ Mapbox HTTP {response.status_code}: {response.text[:200]}")
                    return None
                    
        except Exception as e:
            print(f"❌ Mapbox exception: {e}")
            return None
    
    def calculate_haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Tính khoảng đường chim bay (Haversine formula) - km"""
        R = 6371  # Bán kính trái đất (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return round(R * c, 2)

distance_service = DistanceService()