from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from app.db.mongodb import get_database
from app.models.review_model import ReviewCreate, ReviewUpdate, ReviewResponse
from app.services.review_service import ReviewService
from app.core.security import get_current_user

router = APIRouter(prefix="/reviews", tags=["Review"])

@router.post("/product/{product_id}", response_model=ReviewResponse)
async def create_review(
    product_id: str,
    review_in: ReviewCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Tạo đánh giá mới cho sản phẩm"""
    service = ReviewService(db)
    
    user_name = getattr(current_user, "full_name", None) or getattr(current_user, "username", "Người dùng")
    user_avatar = getattr(current_user, "avatar", None)
    
    return await service.create_review(
        product_id=product_id,
        user_id=str(current_user.id),
        user_name=user_name,
        review_data=review_in.model_dump(),
        user_avatar=user_avatar
    )

@router.get("/product/{product_id}")
async def get_product_reviews(
    product_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    rating: Optional[int] = Query(None, ge=1, le=5),
    db = Depends(get_database)
):
    """Lấy danh sách đánh giá của sản phẩm"""
    service = ReviewService(db)
    return await service.get_reviews_by_product(
        product_id=product_id,
        skip=skip,
        limit=limit,
        rating_filter=rating
    )

@router.get("/product/{product_id}/user-review")
async def get_user_review(
    product_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy đánh giá của current user cho sản phẩm"""
    service = ReviewService(db)
    return await service.get_user_review(product_id, str(current_user.id))

@router.get("/my-reviews")
async def get_my_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy tất cả đánh giá của người dùng hiện tại"""
    service = ReviewService(db)
    return await service.get_user_reviews(str(current_user.id), skip, limit)

@router.get("/{review_id}")
async def get_review(
    review_id: str,
    db = Depends(get_database)
):
    """Lấy chi tiết đánh giá"""
    service = ReviewService(db)
    review = await service.get_review_by_id(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Không tìm thấy đánh giá")
    return review

@router.put("/{review_id}")
async def update_review(
    review_id: str,
    review_update: ReviewUpdate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Cập nhật đánh giá"""
    service = ReviewService(db)
    update_data = review_update.model_dump(exclude_unset=True)
    return await service.update_review(review_id, str(current_user.id), update_data)

@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Xóa đánh giá"""
    service = ReviewService(db)
    is_admin = getattr(current_user, "role", "") == "admin"
    return await service.delete_review(review_id, str(current_user.id), is_admin)

@router.post("/{review_id}/helpful")
async def mark_review_helpful(
    review_id: str,
    db = Depends(get_database)
):
    """Đánh dấu đánh giá hữu ích"""
    service = ReviewService(db)
    return await service.mark_helpful(review_id)

@router.get("/product/{product_id}/stats")
async def get_review_stats(
    product_id: str,
    db = Depends(get_database)
):
    """Lấy thống kê đánh giá của sản phẩm"""
    service = ReviewService(db)
    return await service.get_review_stats(product_id)