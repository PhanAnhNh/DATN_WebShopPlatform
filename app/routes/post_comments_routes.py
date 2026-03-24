from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.post_comments_model import PostCommentCreate, PostCommentResponse, PostCommentUpdate
from app.services.post_comments_services import PostCommentService
from app.db.mongodb import get_database
from app.core.security import get_current_user

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
async def get_comments(post_id: str, db = Depends(get_database)):
    service = PostCommentService(db)
    comments = await service.get_comments_by_post(post_id)
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