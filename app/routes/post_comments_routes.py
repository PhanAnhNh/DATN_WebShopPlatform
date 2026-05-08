from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from app.models.post_comments_model import PostCommentCreate, PostCommentResponse, PostCommentUpdate
from app.services.post_comments_services import PostCommentService
from app.db.mongodb import get_database
from app.core.security import CurrentUser, get_current_user, get_current_user_optional

router = APIRouter(prefix="/comments", tags=["Comments"])

@router.post("/", response_model=PostCommentResponse)  # SỬA: response_model thành PostCommentResponse
async def post_comment(
    comment_in: PostCommentCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = PostCommentService(db)
    return await service.create_comment(str(current_user.id), comment_in.dict())

@router.get("/{post_id}", response_model=List[PostCommentResponse])
async def get_comments(
    post_id: str, 
    db = Depends(get_database),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    service = PostCommentService(db)
    current_user_id = str(current_user.id) if current_user else None
    comments = await service.get_comments_by_post(post_id, current_user_id)
    return comments

@router.put("/{comment_id}")
async def update_comment(
    comment_id: str,
    update_data: PostCommentUpdate,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    service = PostCommentService(db)
    updated = await service.update_comment(
        comment_id,
        str(current_user.id),
        update_data
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Comment không tồn tại hoặc bạn không có quyền sửa"
        )
    return {"message": "Cập nhật comment thành công"}

@router.delete("/{comment_id}")
async def delete_comment(
    comment_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_database)
):
    service = PostCommentService(db)
    deleted = await service.delete_comment(
        comment_id,
        str(current_user.id)
    )
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Comment không tồn tại hoặc bạn không có quyền xóa"
        )
    return {"message": "Xóa comment thành công"}

@router.post("/migrate/hide-old-spam")
async def hide_old_spam_comments(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Cập nhật comment cũ bị spam (chỉ admin)"""
    # Kiểm tra admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ admin mới có quyền")
    
    service = PostCommentService(db)
    
    # Tìm comment có từ khóa xấu
    spam_keywords = ["ngu", "điên", "khùng", "chết", "địt", "cặc", "lồn", "đm", "vcl", "kiếm tiền", "click link"]
    
    result = await service.collection.update_many(
        {
            "$or": [
                {"content": {"$regex": "|".join(spam_keywords), "$options": "i"}},
                {"is_hidden_by_ai": {"$exists": False}}
            ]
        },
        {
            "$set": {
                "is_hidden_by_ai": True,
                "ai_moderation": {
                    "is_spam": True,
                    "is_toxic": True,
                    "confidence": 0.9,
                    "categories": ["spam", "toxic"],
                    "moderated_at": datetime.utcnow()
                }
            }
        }
    )
    
    return {
        "message": f"Đã cập nhật {result.modified_count} comment",
        "modified_count": result.modified_count
    }