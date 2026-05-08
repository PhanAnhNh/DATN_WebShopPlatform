# app/services/ai_moderation_service.py
import os

import httpx
from typing import Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

class AIModerationService:
    def __init__(self, db):
        self.db = db
        self.api_key = os.getenv("OPENAI_API_KEY", "")  
        self.api_url = "https://api.openai.com/v1/moderations" 
        
    async def moderate_comment(self, content: str) -> Dict[str, Any]:
        """
        Kiểm tra comment có bị spam hoặc tiêu cực không
        Returns: {
            "is_spam": bool,
            "is_toxic": bool,
            "confidence": float,
            "categories": list
        }
        """
        try:
            # Cách 1: Dùng OpenAI Moderation API (nếu có key)
            if self.api_key and self.api_key != "YOUR_API_KEY":
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={"input": content}
                    )
                    if response.status_code == 200:
                        result = response.json()
                        categories = result["results"][0]["categories"]
                        return {
                            "is_spam": categories.get("spam", False),
                            "is_toxic": any([
                                categories.get("hate", False),
                                categories.get("harassment", False),
                                categories.get("violence", False)
                            ]),
                            "confidence": result["results"][0]["category_scores"].get("spam", 0),
                            "categories": [k for k, v in categories.items() if v]
                        }
            
            # Cách 2: Dùng rule-based fallback (đơn giản, không cần API)
            return self._rule_based_moderation(content)
            
        except Exception as e:
            print(f"Error moderating comment: {e}")
            # Fallback: không chặn comment nếu AI lỗi
            return {"is_spam": False, "is_toxic": False, "confidence": 0, "categories": []}
    
    def _rule_based_moderation(self, content: str) -> Dict[str, Any]:
        """
        Rule-based moderation (fallback khi không có AI)
        """
        content_lower = content.lower()
        
        # Danh sách từ khóa spam
        spam_keywords = [
            "kiếm tiền", "làm giàu", "click vào link", 
            "đăng ký ngay", "đầu tư lợi nhuận cao", "việc nhẹ lương cao", "kiếm tiền online",
            "app kiếm tiền", "chuyển khoản trước", "vay nóng", "lừa đảo", "scam", "spam",
            "kéo tài xỉu", "chấm để nhận link",
            "https://", "http://", "bit.ly", "tinyurl", "t.co"
        ]
        
        # Danh sách từ khóa toxic
        toxic_keywords = [
            "chết", "ngu", "điên", "khùng", "chửi", "đmm", "đm", 
            "clgt", "vcl", "cặc", "lồn", "địt", "đụ", "cút"
        ]
        
        is_spam = any(keyword in content_lower for keyword in spam_keywords)
        is_toxic = any(keyword in content_lower for keyword in toxic_keywords)
        
        return {
            "is_spam": is_spam,
            "is_toxic": is_toxic,
            "confidence": 0.8 if (is_spam or is_toxic) else 0,
            "categories": ["spam"] if is_spam else (["toxic"] if is_toxic else [])
        }