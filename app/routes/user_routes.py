from fastapi import APIRouter, HTTPException, status, Depends
from app.models.user_model import UserCreate, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Người dùng"])

def get_user_service():
    return UserService()

@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    user_id = await user_service.create_user(user_in)
    if not user_id:
        raise HTTPException(status_code=400, detail="Username hoặc Email đã tồn tại")
    return {"message": "Tạo người dùng thành công", "user_id": user_id}

@router.get("/")
async def list_users(
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.get_all_users()

@router.put("/{user_id}")
async def update_user_info(
    user_id: str,
    user_update: UserUpdate,
    user_service: UserService = Depends(get_user_service)
):
    success = await user_service.update_user(user_id, user_update)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {"message": "Cập nhật thành công"}

@router.delete("/{user_id}")
async def remove_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    return {"message": "Xóa người dùng thành công"}


