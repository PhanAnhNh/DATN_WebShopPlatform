# app/services/distance_service.py
import httpx
from typing import Optional, Dict
import json
import os
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
        # Mapbox yêu cầu format: lng,lat;lng,lat
        # LƯU Ý: Không có dấu cách, phân cách bằng dấu chấm phẩy
        coordinates = f"{lng1},{lat1};{lng2},{lat2}"
        
        # URL đầy đủ
        url = f"{self.base_url}/{coordinates}"
        
        # Tham số query string
        params = {
            "access_token": self.access_token,
            "geometries": "geojson",
            "overview": "simplified",
            "steps": "false",
            "alternatives": "false"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                print(f"Calling Mapbox API...")
                print(f"URL: {url}")
                print(f"Params: {params}")
                
                response = await client.get(url, params=params)
                
                print(f"Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('code') == 'Ok' and data.get('routes'):
                        route = data['routes'][0]
                        distance_km = route['distance'] / 1000
                        duration_min = route['duration'] / 60
                        
                        print(f"✅ Mapbox: {distance_km:.2f} km, {duration_min:.1f} mins")
                        return {
                            "distance_km": round(distance_km, 2),
                            "duration_min": round(duration_min, 1)
                        }
                    else:
                        print(f"Mapbox error code: {data.get('code')}")
                        print(f"Response: {json.dumps(data, indent=2)[:500]}")
                        return None
                else:
                    print(f"HTTP Error: {response.status_code}")
                    print(f"Response: {response.text[:500]}")
                    return None
                    
            except Exception as e:
                print(f"Exception: {e}")
                import traceback
                traceback.print_exc()
                return None

distance_service = DistanceService()