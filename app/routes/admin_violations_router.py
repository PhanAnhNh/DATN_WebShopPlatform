# app/routes/admin_violations_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.db.mongodb import get_database
from app.core.security import get_current_admin
from app.services.ai_moderation_service import AIModerationService
from app.services.admin_notification_service import AdminNotificationService

router = APIRouter(prefix="/admin/violations", tags=["Admin Violations"])

@router.get("/posts")
async def get_violated_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """Lấy danh sách bài viết bị ẩn do vi phạm"""
    posts_collection = db["social_posts"]
    users_collection = db["users"]
    
    skip = (page - 1) * limit
    
    # Tìm bài viết bị ẩn bởi AI
    query = {
        "$or": [
            {"hidden_by_ai": True},
            {"hidden_by_report": True},
            {"hidden_by_ban": True}
        ],
        "is_permanently_deleted": False
    }
    
    total = await posts_collection.count_documents(query)
    
    cursor = posts_collection.find(query).sort("hidden_at", -1).skip(skip).limit(limit)
    
    posts = []
    async for post in cursor:
        # Lấy thông tin tác giả
        author = await users_collection.find_one({"_id": post["author_id"]})
        
        posts.append({
            "_id": str(post["_id"]),
            "content": post.get("content", "")[:200],
            "images": post.get("images", []),
            "author": {
                "id": str(author["_id"]) if author else None,
                "name": author.get("full_name") or author.get("username") if author else "Unknown",
                "avatar": author.get("avatar_url") if author else None
            },
            "hidden_by_ai": post.get("hidden_by_ai", False),
            "hidden_by_report": post.get("hidden_by_report", False),
            "hidden_by_ban": post.get("hidden_by_ban", False),
            "ai_moderation_result": post.get("ai_moderation_result"),
            "hidden_at": post.get("hidden_at"),
            "created_at": post.get("created_at")
        })
    
    return {
        "data": posts,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@router.put("/posts/{post_id}/restore")
async def restore_post(
    post_id: str,
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """Khôi phục bài viết đã bị ẩn (nếu admin cho rằng không vi phạm)"""
    posts_collection = db["social_posts"]
    
    result = await posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$set": {
                "is_active": True,
                "hidden_by_ai": False,
                "hidden_by_report": False,
                "updated_at": datetime.utcnow()
            },
            "$unset": {
                "ai_moderation_result": "",
                "hidden_at": ""
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    
    return {"message": "Đã khôi phục bài viết"}

@router.delete("/posts/{post_id}/permanent")
async def permanently_delete_violated_post(
    post_id: str,
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """Xóa vĩnh viễn bài viết vi phạm"""
    posts_collection = db["social_posts"]
    
    result = await posts_collection.delete_one({"_id": ObjectId(post_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    
    return {"message": "Đã xóa vĩnh viễn bài viết"}

@router.get("/users/banned")
async def get_banned_users(
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """Lấy danh sách tài khoản bị cấm"""
    users_collection = db["users"]
    
    banned_users = []
    cursor = users_collection.find({"is_banned": True})
    
    async for user in cursor:
        banned_users.append({
            "_id": str(user["_id"]),
            "full_name": user.get("full_name"),
            "username": user.get("username"),
            "avatar_url": user.get("avatar_url"),
            "banned_reason": user.get("banned_reason"),
            "banned_at": user.get("banned_at"),
            "banned_by": user.get("banned_by")
        })
    
    return banned_users

@router.post("/users/{user_id}/ban")
async def ban_user_account(
    user_id: str,
    reason: str = Query(..., description="Lý do cấm tài khoản"),
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """Cấm tài khoản người dùng"""
    ai_service = AIModerationService(db)
    
    success = await ai_service.ban_user(user_id, reason, str(current_admin.id))
    
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    # Gửi thông báo cho user bị cấm (nếu cần)
    # ...
    
    return {"message": f"Đã cấm tài khoản. Lý do: {reason}"}

@router.post("/users/{user_id}/unban")
async def unban_user_account(
    user_id: str,
    db = Depends(get_database),
    current_admin = Depends(get_current_admin)
):
    """Mở khóa tài khoản người dùng"""
    ai_service = AIModerationService(db)
    
    success = await ai_service.unban_user(user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    return {"message": "Đã mở khóa tài khoản"}