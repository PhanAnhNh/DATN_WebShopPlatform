from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from app.db.mongodb import get_database
from app.services.admin_dashboard_service import AdminService
from app.core.security import create_access_token, verify_password
from app.services.admin_permission import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin"])

class AdminLoginRequest(BaseModel):
    login_identifier: str
    password: str

@router.post("/login")
async def admin_login(data: AdminLoginRequest, db=Depends(get_database)):
    # Tìm user
    user = await db["users"].find_one({
        "$or": [
            {"email": data.login_identifier},
            {"username": data.login_identifier}
        ]
    })

    if not user:
        raise HTTPException(status_code=401, detail="Tài khoản không tồn tại")

    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản trị")

    if not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Sai mật khẩu")

    # SỬA Ở ĐÂY: create_access_token nhận subject, không phải data
    token = create_access_token(subject=str(user["_id"]))

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user.get("email", ""),
            "role": user["role"]
        }
    }

@router.post("/logout")
async def admin_logout(
    token: str = Header(...),
    admin = Depends(get_current_admin)
):
    return {"message": "Đăng xuất thành công"}

@router.get("/dashboard")
async def dashboard_stats(
        db=Depends(get_database),
        admin=Depends(get_current_admin)
):
    service = AdminService(db)
    return await service.get_dashboard_stats()

@router.get("/post-category")
async def post_category_stats(
        db=Depends(get_database),
        admin=Depends(get_current_admin)
):
    service = AdminService(db)
    return await service.get_category_stats()

@router.get("/new-users")
async def new_users(
        db=Depends(get_database),
        admin=Depends(get_current_admin)
):
    service = AdminService(db)
    return await service.get_new_users()

@router.get("/new-shops")
async def new_shops(
        db=Depends(get_database),
        admin=Depends(get_current_admin)
):
    service = AdminService(db)
    return await service.get_new_shops()