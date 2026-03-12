from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.services.review_shop_service import ShopReviewService
from app.models.reviews_shop_model import ShopReviewCreate
from app.core.security import get_current_user


router = APIRouter(prefix="/shop-reviews", tags=["Shop Reviews"])


@router.post("/")
async def create_review(
    review: ShopReviewCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ShopReviewService(db)

    return await service.create_review(
        str(current_user.id),
        review.dict()
    )


@router.get("/{shop_id}")
async def get_reviews(
    shop_id: str,
    db = Depends(get_database)
):

    service = ShopReviewService(db)

    return await service.get_shop_reviews(shop_id)

@router.put("/{review_shop_id}")
async def update_review(
    review_shop_id: str,
    data: dict,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ShopReviewService(db)

    return await service.update_review(
        review_shop_id,
        str(current_user.id),
        data
    )

@router.delete("/{review_shop_id}")
async def delete_review(
    review_shop_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ShopReviewService(db)

    return await service.delete_review(
        review_shop_id,
        str(current_user.id)
    )