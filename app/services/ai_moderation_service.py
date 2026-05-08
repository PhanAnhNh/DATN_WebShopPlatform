# app/services/ai_moderation_service.py
import os
import google.generativeai as genai
from typing import Dict, Any
import json

class AIModerationService:
    def __init__(self, db):
        self.db = db
        
        # Cấu hình Gemini API
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')  # Model miễn phí
            self.use_gemini = True
            print("✅ Gemini AI đã được khởi tạo")
        else:
            self.use_gemini = False
            print("⚠️ Không tìm thấy GEMINI_API_KEY, sử dụng rule-based fallback")
        
    async def moderate_comment(self, content: str) -> Dict[str, Any]:
        """
        Kiểm tra comment có bị spam hoặc tiêu cực không
        """
        print(f"🔍 Đang kiểm duyệt comment: '{content}'")
        
        try:
            if self.use_gemini:
                result = await self._gemini_moderation(content)
                print(f"✅ Gemini kết luận: {result}")
                return result
            else:
                result = self._rule_based_moderation(content)
                print(f"⚠️ Rule-based kết luận: {result}")
                return result
        except Exception as e:
            print(f"❌ Error moderating comment: {e}")
            return self._rule_based_moderation(content)
    
    async def _gemini_moderation(self, content: str) -> Dict[str, Any]:
        """
        Dùng Gemini AI để kiểm duyệt nội dung
        """
        prompt = f"""
        Bạn là một hệ thống kiểm duyệt nội dung. Hãy phân tích comment sau và trả về JSON:
        
        Comment: "{content}"
        
        Xác định:
        1. is_spam: true nếu comment là spam (quảng cáo, link lừa đảo, nội dung vô nghĩa lặp lại)
        2. is_toxic: true nếu comment có nội dung tiêu cực, xúc phạm, chửi bới, kích động bạo lực
        3. reason: lý do ngắn gọn (tiếng Việt)
        
        Chỉ trả về JSON, không giải thích thêm. Ví dụ:
        {{"is_spam": false, "is_toxic": false, "reason": "bình thường"}}
        {{"is_spam": true, "is_toxic": false, "reason": "chứa link quảng cáo"}}
        {{"is_spam": false, "is_toxic": true, "reason": "chứa từ ngữ xúc phạm"}}
        """
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Lọc JSON từ response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            result = json.loads(result_text)
            
            return {
                "is_spam": result.get("is_spam", False),
                "is_toxic": result.get("is_toxic", False),
                "confidence": 0.9,
                "categories": ["spam"] if result.get("is_spam") else (["toxic"] if result.get("is_toxic") else []),
                "reason": result.get("reason", "")
            }
            
        except Exception as e:
            print(f"Gemini moderation error: {e}")
            return self._rule_based_moderation(content)
    
    def _rule_based_moderation(self, content: str) -> Dict[str, Any]:
        """
        Rule-based moderation (fallback khi không có AI)
        """
        content_lower = content.lower()
        
        spam_keywords = [
            "kiếm tiền", "làm giàu", "click vào link", "đăng ký ngay",
            "đầu tư", "việc nhẹ lương cao", "kiếm tiền online",
            "app kiếm tiền", "chuyển khoản", "vay nóng", "lừa đảo",
            "kéo tài xỉu", "https://", "http://", "bit.ly", "t.co"
        ]
        
        toxic_keywords = [
            "chết", "ngu", "điên", "khùng", "chửi", "đmm", "đm",
            "clgt", "vcl", "cặc", "lồn", "địt", "đụ", "cút",
            "mày", "tao", "con chó", "thằng ngu"
        ]
        
        is_spam = any(keyword in content_lower for keyword in spam_keywords)
        is_toxic = any(keyword in content_lower for keyword in toxic_keywords)
        
        return {
            "is_spam": is_spam,
            "is_toxic": is_toxic,
            "confidence": 0.8 if (is_spam or is_toxic) else 0,
            "categories": ["spam"] if is_spam else (["toxic"] if is_toxic else [])
        }