# app/services/ai_moderation_service.py
import os
import google.generativeai as genai
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from bson import ObjectId
import requests

class AIModerationService:
    def __init__(self, db):
        self.db = db
        self.users_collection = db["users"]
        self.posts_collection = db["social_posts"]
        self.notification_service = None
        
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

        self.vision_api_key = os.getenv("GOOGLE_VISION_API_KEY", "")    


        if self.vision_api_key:
            print(f"✅ Google Cloud Vision API Key đã được cấu hình: {self.vision_api_key[:10]}...")
            self.use_vision = True
        else:
            self.use_vision = False
            print("⚠️ Không tìm thấy GOOGLE_VISION_API_KEY")

    def set_notification_service(self, notification_service):
        """Set notification service để gửi thông báo cho admin"""
        self.notification_service = notification_service

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
    
    async def moderate_post_text(self, content: str) -> Dict[str, Any]:
        """
        Kiểm tra nội dung text của bài đăng có 18+ hoặc không phù hợp không
        """
        if not content:
            return {"is_adult": False, "is_harmful": False, "reason": "Không có nội dung", "should_hide": False}
        
        print(f"🔍 Đang kiểm duyệt bài đăng text: '{content[:100]}...'")
        
        try:
            if self.use_gemini:
                result = await self._gemini_moderate_post(content)
            else:
                result = self._rule_based_moderate_post(content)
            
            # Quyết định ẩn bài viết
            result["should_hide"] = result.get("is_adult", False) or result.get("is_harmful", False)
            
            return result
        except Exception as e:
            print(f"❌ Error moderating post text: {e}")
            return {"is_adult": False, "is_harmful": False, "reason": "Lỗi kiểm duyệt", "should_hide": False}

    async def _gemini_moderate_post(self, content: str) -> Dict[str, Any]:
        """
        Dùng Gemini AI để kiểm duyệt nội dung bài đăng (18+, bạo lực, quấy rối)
        """
        prompt = f"""
        Bạn là một hệ thống kiểm duyệt nội dung mạng xã hội. Hãy phân tích bài đăng sau và trả về JSON:
        
        Nội dung: "{content}"
        
        Đánh giá các tiêu chí:
        1. is_adult: true nếu nội dung có nội dung người lớn (18+), khiêu dâm, nhạy cảm về giới tính
        2. is_violent: true nếu nội dung có bạo lực, đe dọa, kích động thù địch
        3. is_harassment: true nếu nội dung quấy rối, xúc phạm cá nhân hoặc tập thể
        4. reason: lý do ngắn gọn bằng tiếng Việt
        
        Chỉ trả về JSON, không giải thích thêm. Ví dụ:
        {{"is_adult": false, "is_violent": false, "is_harassment": false, "reason": "bình thường"}}
        {{"is_adult": true, "is_violent": false, "is_harassment": false, "reason": "chứa nội dung người lớn 18+"}}
        """
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Lọc JSON
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            result = json.loads(result_text)
            
            return {
                "is_adult": result.get("is_adult", False),
                "is_violent": result.get("is_violent", False),
                "is_harassment": result.get("is_harassment", False),
                "reason": result.get("reason", ""),
                "confidence": 0.9
            }
            
        except Exception as e:
            print(f"Gemini moderation error: {e}")
            return self._rule_based_moderate_post(content)
        
    def _rule_based_moderate_post(self, content: str) -> Dict[str, Any]:
        """
        Rule-based moderation cho bài đăng (fallback)
        """
        content_lower = content.lower()
        
        # Từ khóa 18+ / nhạy cảm
        adult_keywords = [
            "sex", "địt", "đụ", "cặc", "lồn", "bướm", "chim", "buồi",
            "khiêu dâm", "nude", "ảnh nóng", "sex", "jav", "phim sex",
            "người lớn", "18+", "nứng", "lên đỉnh", "xuất tinh"
        ]
        
        # Từ khóa bạo lực
        violent_keywords = [
            "giết", "chém", "đâm", "đánh chết", "bạo lực", "xé xác",
            "thiêu sống", "chặt", "băm", "dìm"
        ]
        
        # Từ khóa quấy rối
        harassment_keywords = [
            "ngu", "điên", "khùng", "chó", "lợn", "thằng điên",
            "con đĩ", "thằng khốn", "đồ ngu"
        ]
        
        is_adult = any(kw in content_lower for kw in adult_keywords)
        is_violent = any(kw in content_lower for kw in violent_keywords)
        is_harassment = any(kw in content_lower for kw in harassment_keywords)
        
        reason = []
        if is_adult: reason.append("chứa nội dung người lớn 18+")
        if is_violent: reason.append("chứa nội dung bạo lực")
        if is_harassment: reason.append("chứa nội dung quấy rối")
        
        return {
            "is_adult": is_adult,
            "is_violent": is_violent,
            "is_harassment": is_harassment,
            "reason": ", ".join(reason) if reason else "bình thường",
            "confidence": 0.8 if (is_adult or is_violent or is_harassment) else 0
        }
    
    # ==================== MODERATE IMAGES ====================
    
    async def moderate_images(self, image_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Kiểm tra danh sách ảnh có nội dung người lớn/không phù hợp không
        Trả về danh sách kết quả cho từng ảnh
        """
        if not self.use_vision or not image_urls:
            return [{"is_adult": False, "is_violent": False, "should_hide": False} for _ in image_urls] if image_urls else []
        
        results = []
        for url in image_urls:
            result = await self._moderate_single_image(url)
            results.append(result)
        
        return results
    
    async def _moderate_single_image(self, image_url: str) -> Dict[str, Any]:
        """
        Dùng Google Cloud Vision REST API với API Key để kiểm tra ảnh
        """
        if not self.use_vision:
            return {"is_adult": False, "is_violent": False, "should_hide": False, "reason": "Vision API chưa được cấu hình"}
        
        try:
            # Endpoint với API Key
            endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={self.vision_api_key}"
            
            # Tạo payload
            payload = {
                "requests": [
                    {
                        "image": {"source": {"imageUri": image_url}},
                        "features": [{"type": "SAFE_SEARCH_DETECTION"}]
                    }
                ]
            }
            
            # Gọi API
            import requests
            response = requests.post(endpoint, json=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Vision API lỗi: {response.status_code} - {response.text}")
                return {"is_adult": False, "is_violent": False, "should_hide": False, "reason": f"Lỗi API: {response.status_code}"}
            
            data = response.json()
            
            if "responses" not in data or not data["responses"]:
                return {"is_adult": False, "is_violent": False, "should_hide": False, "reason": "Không có kết quả"}
            
            safe_search = data["responses"][0].get("safeSearchAnnotation", {})
            
            # Map likelihood string sang số
            likelihood_map = {
                "UNKNOWN": 0,
                "VERY_UNLIKELY": 1,
                "UNLIKELY": 2,
                "POSSIBLE": 3,
                "LIKELY": 4,
                "VERY_LIKELY": 5
            }
            
            adult_level = likelihood_map.get(safe_search.get("adult", "UNKNOWN"), 0)
            violence_level = likelihood_map.get(safe_search.get("violence", "UNKNOWN"), 0)
            
            # Quyết định ẩn (LIKELY hoặc VERY_LIKELY)
            is_adult = adult_level >= 4
            is_violent = violence_level >= 4
            
            should_hide = is_adult or is_violent
            
            reason = []
            if is_adult:
                reason.append(f"nội dung người lớn ({safe_search.get('adult', 'UNKNOWN')})")
            if is_violent:
                reason.append(f"nội dung bạo lực ({safe_search.get('violence', 'UNKNOWN')})")
            
            return {
                "is_adult": is_adult,
                "is_violent": is_violent,
                "should_hide": should_hide,
                "reason": ", ".join(reason) if reason else "bình thường",
                "scores": {
                    "adult": safe_search.get("adult", "UNKNOWN"),
                    "violence": safe_search.get("violence", "UNKNOWN"),
                    "racy": safe_search.get("racy", "UNKNOWN")
                }
            }
            
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout khi gọi Vision API: {image_url}")
            return {"is_adult": False, "is_violent": False, "should_hide": False, "reason": "Timeout"}
        except Exception as e:
            print(f"❌ Lỗi khi gọi Vision API: {e}")
            return {"is_adult": False, "is_violent": False, "should_hide": False, "reason": f"Lỗi: {str(e)}"}
    
    async def moderate_post(self, post: dict, content: str, image_urls: List[str]) -> Dict[str, Any]:
        """
        Kiểm duyệt toàn bộ bài đăng (cả text và ảnh)
        Trả về kết quả và quyết định ẩn bài viết
        """
        # Kiểm tra text
        text_result = await self.moderate_post_text(content) if content else {"is_adult": False, "is_harmful": False}
        
        # Kiểm tra images
        image_results = await self.moderate_images(image_urls) if image_urls else []
        
        # Tổng hợp kết quả
        has_adult_text = text_result.get("is_adult", False)
        has_harmful_text = text_result.get("is_harmful", False) or text_result.get("is_violent", False) or text_result.get("is_harassment", False)
        
        has_adult_image = any(img.get("is_adult", False) for img in image_results)
        has_violent_image = any(img.get("is_violent", False) for img in image_results)
        
        should_hide = has_adult_text or has_harmful_text or has_adult_image or has_violent_image
        
        # Xây dựng lý do
        reasons = []
        if has_adult_text:
            reasons.append(f"nội dung text: {text_result.get('reason', '')}")
        if has_harmful_text:
            reasons.append(f"nội dung text tiêu cực: {text_result.get('reason', '')}")
        if has_adult_image:
            reasons.append("hình ảnh người lớn")
        if has_violent_image:
            reasons.append("hình ảnh bạo lực")
        
        return {
            "should_hide": should_hide,
            "text_result": text_result,
            "image_results": image_results,
            "reasons": reasons,
            "moderated_at": datetime.utcnow()
        }
    
    # ==================== AUTO HIDE POST AND NOTIFY ADMIN ====================
    
    async def process_and_hide_post_if_needed(
        self, 
        post_id: str, 
        content: str, 
        image_urls: List[str],
        author_id: str,
        author_name: str
    ) -> bool:
        """
        Xử lý bài đăng: kiểm duyệt, ẩn nếu vi phạm, gửi thông báo cho admin
        Trả về True nếu bài viết bị ẩn, False nếu không
        """
        # Lấy bài viết từ database
        post = await self.posts_collection.find_one({"_id": ObjectId(post_id)})
        if not post:
            print(f"Không tìm thấy bài viết {post_id}")
            return False
        
        # Kiểm duyệt
        moderation_result = await self.moderate_post(post, content, image_urls)
        
        if moderation_result["should_hide"]:
            # Ẩn bài viết
            await self.posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                {
                    "$set": {
                        "is_active": False,
                        "hidden_by_ai": True,
                        "ai_moderation_result": moderation_result,
                        "hidden_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            print(f"🚫 Bài viết {post_id} đã bị ẩn tự động. Lý do: {moderation_result['reasons']}")
            
            # Gửi thông báo cho admin
            await self._notify_admin_about_violation(
                post_id=post_id,
                author_id=author_id,
                author_name=author_name,
                content=content[:200],
                reasons=moderation_result["reasons"],
                image_count=len(image_urls)
            )
            
            return True
        
        return False
    
    async def _notify_admin_about_violation(
        self,
        post_id: str,
        author_id: str,
        author_name: str,
        content: str,
        reasons: List[str],
        image_count: int
    ):
        """
        Gửi thông báo cho admin khi phát hiện bài viết vi phạm
        """
        if not self.notification_service:
            print("⚠️ Chưa set notification service, không thể gửi thông báo")
            return
        
        # Lấy danh sách admin
        admin_users = await self.users_collection.find({"role": "admin"}).to_list(length=None)
        
        reason_text = ", ".join(reasons)
        
        for admin in admin_users:
            await self.notification_service.create_notification(
                user_id=str(admin["_id"]),
                type="violation_post",
                title="⚠️ Bài viết vi phạm đã bị ẩn tự động",
                message=f"Người dùng {author_name} vừa đăng bài viết có nội dung không phù hợp ({reason_text}).\nNội dung: {content[:100]}...\nSố lượng ảnh: {image_count}",
                reference_id=post_id,
                image_url=None
            )
    
    # ==================== BAN USER ACCOUNT ====================
    
    async def ban_user(self, user_id: str, reason: str, admin_id: str) -> bool:
        """
        Cấm tài khoản người dùng (khóa tạm thời hoặc vĩnh viễn)
        """
        result = await self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_active": False,
                    "is_banned": True,
                    "banned_reason": reason,
                    "banned_by": admin_id,
                    "banned_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            # Ẩn tất cả bài viết của user bị cấm
            await self.posts_collection.update_many(
                {"author_id": ObjectId(user_id)},
                {
                    "$set": {
                        "is_active": False,
                        "hidden_by_ban": True,
                        "banned_reason": reason,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            print(f"🔨 Đã cấm tài khoản {user_id}. Lý do: {reason}")
            return True
        
        return False
    
    async def unban_user(self, user_id: str) -> bool:
        """
        Mở khóa tài khoản người dùng
        """
        result = await self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_active": True,
                    "is_banned": False,
                    "updated_at": datetime.utcnow()
                },
                "$unset": {
                    "banned_reason": "",
                    "banned_by": "",
                    "banned_at": ""
                }
            }
        )
        
        if result.modified_count > 0:
            # Khôi phục bài viết (có thể chọn không khôi phục nếu vẫn vi phạm)
            # await self.posts_collection.update_many(
            #     {"author_id": ObjectId(user_id), "hidden_by_ban": True},
            #     {"$set": {"is_active": True, "hidden_by_ban": False}}
            # )
            
            print(f"✅ Đã mở khóa tài khoản {user_id}")
            return True
        
        return False