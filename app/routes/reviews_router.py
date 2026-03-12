from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.models.reviews_model import ProductReviewCreate
from app.core.security import get_current_user
from app.services.reviews_service import ProductReviewService


router = APIRouter(prefix="/product-reviews", tags=["Product Reviews"])


@router.post("/")
async def create_review(
    review: ProductReviewCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ProductReviewService(db)

    return await service.create_review(
        str(current_user.id),
        review.dict()
    )


@router.get("/{product_id}")
async def get_reviews(
    product_id: str,
    db = Depends(get_database)
):

    service = ProductReviewService(db)

    return await service.get_product_reviews(product_id)

@router.put("/{review_id}")
async def update_review(
    review_id: str,
    data: dict,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ProductReviewService(db)

    return await service.update_review(
        review_id,
        str(current_user.id),
        data
    )

@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ProductReviewService(db)

    return await service.delete_review(
        review_id,
        str(current_user.id)
    )