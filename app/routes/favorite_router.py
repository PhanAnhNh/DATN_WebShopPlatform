# app/api/v1/endpoints/favorite.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.db.mongodb import get_database
from app.services.favorite_service import FavoriteService
from app.services.product_service import ProductService
from app.core.security import get_current_user
from app.models.favorite_model import FavoriteResponse

router = APIRouter(prefix="/favorites", tags=["Favorites"])

@router.post("/{product_id}")
async def add_favorite(
    product_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Thêm sản phẩm vào danh sách yêu thích"""
    favorite_service = FavoriteService(db)
    product_service = ProductService(db)
    
    # Kiểm tra sản phẩm tồn tại
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    
    result = await favorite_service.add_favorite(str(current_user.id), product_id)
    if not result:
        raise HTTPException(status_code=400, detail="Sản phẩm đã có trong danh sách yêu thích")
    
    return {"message": "Đã thêm vào yêu thích", "favorite": result}

@router.delete("/{product_id}")
async def remove_favorite(
    product_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Xóa sản phẩm khỏi danh sách yêu thích"""
    favorite_service = FavoriteService(db)
    
    result = await favorite_service.remove_favorite(str(current_user.id), product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sản phẩm không có trong danh sách yêu thích")
    
    return {"message": "Đã xóa khỏi yêu thích"}

@router.get("/check/{product_id}")
async def check_favorite(
    product_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Kiểm tra sản phẩm có trong danh sách yêu thích không"""
    favorite_service = FavoriteService(db)
    
    is_fav = await favorite_service.is_favorite(str(current_user.id), product_id)
    return {"is_favorite": is_fav}

@router.get("/my-favorites")
async def get_my_favorites(
    skip: int = 0,
    limit: int = 20,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy danh sách sản phẩm yêu thích của user hiện tại"""
    favorite_service = FavoriteService(db)
    
    favorites = await favorite_service.get_user_favorites(str(current_user.id), skip, limit)
    total = await favorite_service.get_total_favorites_count(str(current_user.id))
    
    return {
        "data": favorites,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get("/count/{product_id}")
async def get_favorite_count(
    product_id: str,
    db = Depends(get_database)
):
    """Đếm số lượt yêu thích của sản phẩm"""
    favorite_service = FavoriteService(db)
    
    count = await favorite_service.get_favorite_count(product_id)
    return {"product_id": product_id, "favorite_count": count}