from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB, UserUpdate
from app.models.shops_model import ShopUpdate
from app.services.user_service import UserService
from app.services.shop_service import ShopService
from bson import ObjectId
import os
import shutil
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/shop/profile", tags=["Shop Profile"])

@router.get("/")
async def get_shop_profile(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thông tin profile của shop và chủ shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền truy cập"
        )
    
    if not current_user.shop_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn chưa có shop"
        )
    
    # Lấy thông tin shop
    shop = await db["shops"].find_one({"_id": ObjectId(current_user.shop_id)})
    if not shop:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy thông tin shop"
        )
    
    # Format shop data
    shop_data = {
        "id": str(shop["_id"]),
        "name": shop["name"],
        "slug": shop["slug"],
        "description": shop.get("description"),
        "phone": shop.get("phone"),
        "email": shop.get("email"),
        "address": shop.get("address"),
        "province": shop.get("province"),
        "district": shop.get("district"),
        "ward": shop.get("ward"),
        "logo_url": shop.get("logo_url"),
        "banner_url": shop.get("banner_url"),
        "status": shop.get("status"),
        "is_verified": shop.get("is_verified", False),
        "products_count": shop.get("products_count", 0),
        "followers_count": shop.get("followers_count", 0),
        "total_orders": shop.get("total_orders", 0),
        "total_revenue": shop.get("total_revenue", 0),
        "created_at": shop.get("created_at"),
        "updated_at": shop.get("updated_at")
    }
    
    # Format user data
    user_data = {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "gender": current_user.gender,
        "dob": current_user.dob,
        "address": current_user.address,
        "avatar_url": current_user.avatar_url,
        "cover_url": current_user.cover_url,
        "role": current_user.role,
        "created_at": current_user.created_at
    }
    
    return {
        "shop": shop_data,
        "owner": user_data
    }

@router.put("/shop")
async def update_shop_info(
    shop_update: ShopUpdate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Cập nhật thông tin shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền thực hiện"
        )
    
    if not current_user.shop_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn chưa có shop"
        )
    
    service = ShopService(db)
    updated_shop = await service.update_shop(current_user.shop_id, shop_update)
    
    if not updated_shop:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy shop"
        )
    
    return updated_shop

@router.put("/owner")
async def update_owner_info(
    owner_update: UserUpdate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Cập nhật thông tin chủ shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền thực hiện"
        )
    
    service = UserService(db)
    success = await service.update_user(str(current_user.id), owner_update)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy người dùng"
        )
    
    # Lấy thông tin mới
    updated_user = await service.get_user_by_id(str(current_user.id))
    
    return {
        "message": "Cập nhật thông tin thành công",
        "user": updated_user
    }

@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Upload avatar cho chủ shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền thực hiện"
        )
    
    # Kiểm tra file
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File phải là ảnh"
        )
    
    # Tạo thư mục nếu chưa có
    upload_dir = "static/avatars"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Tạo tên file
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"user_{current_user.id}_{datetime.now().timestamp()}{file_ext}"
    file_path = os.path.join(upload_dir, file_name)
    
    # Lưu file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Cập nhật database
    avatar_url = f"/static/avatars/{file_name}"
    await db["users"].update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"avatar_url": avatar_url}}
    )
    
    return {
        "avatar_url": avatar_url,
        "message": "Upload avatar thành công"
    }

@router.post("/upload-logo")
async def upload_shop_logo(
    file: UploadFile = File(...),
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Upload logo cho shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền thực hiện"
        )
    
    if not current_user.shop_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn chưa có shop"
        )
    
    # Kiểm tra file
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File phải là ảnh"
        )
    
    # Tạo thư mục nếu chưa có
    upload_dir = "static/shop_logos"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Tạo tên file
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"shop_{current_user.shop_id}_{datetime.now().timestamp()}{file_ext}"
    file_path = os.path.join(upload_dir, file_name)
    
    # Lưu file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Cập nhật database
    logo_url = f"/static/shop_logos/{file_name}"
    await db["shops"].update_one(
        {"_id": ObjectId(current_user.shop_id)},
        {"$set": {"logo_url": logo_url}}
    )
    
    return {
        "logo_url": logo_url,
        "message": "Upload logo thành công"
    }

@router.post("/upload-banner")
async def upload_shop_banner(
    file: UploadFile = File(...),
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Upload banner cho shop
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền thực hiện"
        )
    
    if not current_user.shop_id:
        raise HTTPException(
            status_code=400,
            detail="Bạn chưa có shop"
        )
    
    # Kiểm tra file
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File phải là ảnh"
        )
    
    # Tạo thư mục nếu chưa có
    upload_dir = "static/shop_banners"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Tạo tên file
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"shop_{current_user.shop_id}_{datetime.now().timestamp()}{file_ext}"
    file_path = os.path.join(upload_dir, file_name)
    
    # Lưu file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Cập nhật database
    banner_url = f"/static/shop_banners/{file_name}"
    await db["shops"].update_one(
        {"_id": ObjectId(current_user.shop_id)},
        {"$set": {"banner_url": banner_url}}
    )
    
    return {
        "banner_url": banner_url,
        "message": "Upload banner thành công"
    }

@router.post("/change-password")
async def change_password(
    data: dict,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Đổi mật khẩu
    """
    if current_user.role != "shop_owner":
        raise HTTPException(
            status_code=403,
            detail="Không có quyền thực hiện"
        )
    
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    
    if not old_password or not new_password:
        raise HTTPException(
            status_code=400,
            detail="Vui lòng nhập đầy đủ mật khẩu"
        )
    
    if len(new_password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu mới phải có ít nhất 6 ký tự"
        )
    
    # Lấy user từ DB
    user = await db["users"].find_one({"_id": ObjectId(current_user.id)})
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy người dùng"
        )
    
    # Kiểm tra mật khẩu cũ
    from app.core.security import verify_password, get_password_hash
    if not verify_password(old_password, user["hashed_password"]):
        raise HTTPException(
            status_code=400,
            detail="Mật khẩu cũ không chính xác"
        )
    
    # Cập nhật mật khẩu mới
    new_hashed = get_password_hash(new_password)
    await db["users"].update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"hashed_password": new_hashed}}
    )
    
    return {
        "message": "Đổi mật khẩu thành công"
    }