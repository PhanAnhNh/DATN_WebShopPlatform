# app/routes/admin_profile_router.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.db.mongodb import get_database
from app.core.security import get_current_admin
from app.models.user_model import UserUpdate
from app.routes.shop_profile import upload_to_r2
from app.services.user_service import UserService
from app.services.admin_dashboard_service import AdminService
from bson import ObjectId
from datetime import datetime
import uuid

router = APIRouter(prefix="/admin/profile", tags=["Admin Profile"])

@router.get("/")
async def get_admin_profile(
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    """Lấy thông tin admin hiện tại"""
    user_service = UserService(db)
    user = await user_service.get_user_by_id(str(admin.id))
    
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    # Loại bỏ thông tin nhạy cảm
    user.pop("hashed_password", None)
    
    return user

@router.get("/stats")
async def get_admin_stats(
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    """Lấy thống kê hoạt động của admin"""
    admin_service = AdminService(db)
    stats = await admin_service.get_dashboard_stats()
    return stats

@router.put("/")
async def update_admin_profile(
    update_data: UserUpdate,
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    """Cập nhật thông tin admin"""
    user_service = UserService(db)
    
    success = await user_service.update_user(str(admin.id), update_data)
    
    if not success:
        raise HTTPException(status_code=400, detail="Cập nhật thất bại")
    
    # Lấy thông tin mới
    updated_user = await user_service.get_user_by_id(str(admin.id))
    updated_user.pop("hashed_password", None)
    
    return updated_user

@router.post("/avatar")
async def upload_admin_avatar(
    file: UploadFile = File(...),
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    """Upload ảnh đại diện cho admin lên Cloudflare R2"""
    # Kiểm tra file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Chỉ chấp nhận file ảnh")
    
    # Kiểm tra kích thước (5MB)
    MAX_SIZE = 5 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Kích thước file không được vượt quá 5MB")
    
    # Kiểm tra định dạng file
    file_extension = file.filename.split(".")[-1].lower()
    if file_extension not in ["jpg", "jpeg", "png", "gif", "webp"]:
        raise HTTPException(status_code=400, detail="Định dạng ảnh không được hỗ trợ. Hỗ trợ: jpg, jpeg, png, gif, webp")
    
    try:
        # Tạo tên file unique
        unique_filename = f"admin_avatars/admin_{admin.id}_{uuid.uuid4()}.{file_extension}"
        
        # Upload lên R2
        image_url = await upload_to_r2(
            file_content=content,
            filename=unique_filename,
            content_type=file.content_type
        )
        
        # Cập nhật database với URL mới từ R2
        await db["users"].update_one(
            {"_id": ObjectId(admin.id)},
            {"$set": {"avatar_url": image_url, "updated_at": datetime.utcnow()}}
        )
        
        return {"avatar_url": image_url}
        
    except Exception as error:
        print(f"Error uploading avatar: {error}")
        raise HTTPException(status_code=500, detail=f"Có lỗi xảy ra khi upload ảnh: {str(error)}")

@router.put("/password")
async def change_admin_password(
    data: dict,
    db = Depends(get_database),
    admin = Depends(get_current_admin)
):
    """Đổi mật khẩu admin"""
    from app.core.security import verify_password, get_password_hash
    
    # Kiểm tra mật khẩu hiện tại
    user = await db["users"].find_one({"_id": ObjectId(admin.id)})
    
    if not verify_password(data["current_password"], user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng")
    
    # Cập nhật mật khẩu mới
    new_hashed = get_password_hash(data["new_password"])
    
    await db["users"].update_one(
        {"_id": ObjectId(admin.id)},
        {"$set": {"hashed_password": new_hashed, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Đổi mật khẩu thành công"}