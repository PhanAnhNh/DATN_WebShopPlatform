from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status, Depends
from app.core.security import CurrentUser, get_current_user, get_current_user_optional
from app.db.mongodb import get_database
from app.models.user_model import UserCreate, UserUpdate
from app.services.follow_service import FollowService
from app.services.friend_service import FriendService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Người dùng"])

def get_user_service():
    return UserService()

@router.get("/search")  # Phải ở TRÊN route /{user_id}
async def search_users(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Tìm kiếm người dùng theo tên hoặc username"""
    users_collection = db["users"]
    
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"full_name": {"$regex": keyword, "$options": "i"}},
                    {"username": {"$regex": keyword, "$options": "i"}}
                ],
                "is_active": True
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "full_name": 1,
                "username": 1,
                "avatar_url": 1,
                "bio": 1
            }
        }
    ]
    
    users = []
    cursor = users_collection.aggregate(pipeline)
    async for user in cursor:
        users.append(user)
    
    return users

@router.get("/me")  # Cũng nên đặt trước route động
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user)
):
    """Lấy thông tin user hiện tại"""
    return current_user

@router.get("/{user_id}")
async def get_user_profile(
    user_id: str,
    db = Depends(get_database),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Lấy follow stats
    follow_service = FollowService(db)
    stats = await follow_service.get_follow_stats(user_id)
    
    # Lấy friend count
    friend_service = FriendService(db)
    friends_count = await friend_service.get_friend_count(user_id)
    
    # Trả về thông tin user kèm follow counts và friends count
    return {
        "_id": str(user["_id"]),
        "full_name": user.get("full_name"),
        "username": user.get("username"),
        "avatar_url": user.get("avatar_url"),
        "cover_url": user.get("cover_url"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "location": user.get("location"),
        "bio": user.get("bio"),
        "created_at": user.get("created_at"),
        "followers_count": stats["followers_count"],
        "following_count": stats["following_count"],
        "friends_count": friends_count,
        "posts_count": user.get("posts_count", 0)
    }


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

