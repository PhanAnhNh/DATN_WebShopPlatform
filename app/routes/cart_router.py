from typing import Optional
from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.services.cart_service import CartService
from app.core.security import get_current_user

router = APIRouter(prefix="/cart", tags=["Cart"])

@router.get("/")
async def get_my_cart(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = CartService(db)
    return await service.get_cart(str(current_user.id), db)

@router.post("/add")
async def add_to_cart(
    product_id: str,
    quantity: int,
    variant_id: Optional[str] = None,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = CartService(db)

    return await service.add_to_cart(
        str(current_user.id),
        product_id,
        quantity,
        variant_id
    )

@router.delete("/remove")
async def remove_item(
    product_id: str,
    variant_id: Optional[str] = None,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = CartService(db)
    return await service.remove_from_cart(str(current_user.id), product_id, variant_id)