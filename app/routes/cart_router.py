# routes/cart_router.py
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Query
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
    product_id: str = Query(...),
    quantity: int = Query(...),
    variant_id: Optional[str] = Query(None),
    shop_id: Optional[str] = Query(None),  # Thêm shop_id
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = CartService(db)
    return await service.add_to_cart(
        str(current_user.id),
        product_id,
        quantity,
        variant_id,
        shop_id  # Truyền shop_id vào
    )

@router.get("/count")
async def get_cart_count(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Đếm số lượng sản phẩm trong giỏ hàng (theo item, không theo quantity)"""
    service = CartService(db)
    cart = await service.collection.find_one({"user_id": ObjectId(current_user.id)})
    
    if not cart or "items" not in cart:
        return {"count": 0}
    
    item_count = len(cart["items"])
    return {"count": item_count}

@router.delete("/remove")
async def remove_item(
    product_id: str = Query(...),
    variant_id: Optional[str] = Query(None),
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = CartService(db)
    return await service.remove_from_cart(str(current_user.id), product_id, variant_id)