# app/routes/group_routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId


from app.db.mongodb import get_database
from app.core.security import get_current_user, CurrentUser, get_current_user_optional
from app.models.group_model import GroupCreate, GroupResponse, GroupUpdate
from app.services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["Groups"])

@router.post("/", response_model=GroupResponse)
async def create_group(
    group_data: GroupCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Tạo nhóm mới"""
    service = GroupService(db)
    group = await service.create_group(group_data, str(current_user.id))
    return group

@router.get("/my-groups", response_model=List[GroupResponse])
async def get_my_groups(
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lấy danh sách nhóm của tôi"""
    service = GroupService(db)
    groups = await service.get_my_groups(str(current_user.id))
    return groups

@router.get("/public", response_model=List[GroupResponse])
async def get_public_groups(
    limit: int = Query(20, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db = Depends(get_database)
):
    """Lấy danh sách nhóm công khai"""
    service = GroupService(db)
    user_id = str(current_user.id) if current_user else None
    groups = await service.get_public_groups(user_id, limit, skip)
    return groups

@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db = Depends(get_database)
):
    """Lấy thông tin chi tiết nhóm"""
    service = GroupService(db)
    user_id = str(current_user.id) if current_user else None
    group = await service.get_group_by_id(group_id, user_id)
    if not group:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm")
    return group

@router.post("/{group_id}/join")
async def join_group(
    group_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Tham gia nhóm"""
    service = GroupService(db)
    result = await service.join_group(group_id, str(current_user.id))
    if not result:
        raise HTTPException(status_code=400, detail="Không thể tham gia nhóm")
    return {"message": "Đã gửi yêu cầu tham gia nhóm" if result else "Đã tham gia nhóm"}

@router.post("/{group_id}/leave")
async def leave_group(
    group_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Rời nhóm"""
    service = GroupService(db)
    result = await service.leave_group(group_id, str(current_user.id))
    if not result:
        raise HTTPException(status_code=400, detail="Không thể rời nhóm")
    return {"message": "Đã rời nhóm"}

@router.post("/{group_id}/members/{user_id}")
async def add_member(
    group_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Thêm thành viên (chỉ admin)"""
    service = GroupService(db)
    result = await service.add_member(group_id, str(current_user.id), user_id)
    if not result:
        raise HTTPException(status_code=400, detail="Không thể thêm thành viên")
    return {"message": "Đã thêm thành viên"}

@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Xóa thành viên (chỉ admin)"""
    service = GroupService(db)
    result = await service.remove_member(group_id, str(current_user.id), user_id)
    if not result:
        raise HTTPException(status_code=400, detail="Không thể xóa thành viên")
    return {"message": "Đã xóa thành viên"}

@router.post("/{group_id}/approve/{user_id}")
async def approve_member(
    group_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Duyệt thành viên (chỉ admin, cho nhóm riêng tư)"""
    service = GroupService(db)
    result = await service.approve_member(group_id, str(current_user.id), user_id)
    if not result:
        raise HTTPException(status_code=400, detail="Không thể duyệt thành viên")
    return {"message": "Đã duyệt thành viên"}

@router.put("/{group_id}")
async def update_group(
    group_id: str,
    update_data: GroupUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Cập nhật nhóm (chỉ admin)"""
    service = GroupService(db)
    group = await service.update_group(group_id, str(current_user.id), update_data)
    if not group:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm hoặc không có quyền")
    return group

@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Xóa nhóm (chỉ chủ nhóm)"""
    service = GroupService(db)
    result = await service.delete_group(group_id, str(current_user.id))
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm hoặc không có quyền")
    return {"message": "Đã xóa nhóm"}

@router.get("/{group_id}/members", response_model=List[dict])
async def get_group_members(
    group_id: str,
    limit: int = Query(20, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db = Depends(get_database)
):
    """Lấy danh sách thành viên"""
    service = GroupService(db)
    members = await service.get_group_members(group_id, str(current_user.id), limit, skip)
    return members

@router.get("/{group_id}/posts")
async def get_group_posts(
    group_id: str,
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db = Depends(get_database)
):
    """Lấy bài viết trong nhóm"""
    service = GroupService(db)
    user_id = str(current_user.id) if current_user else None
    posts = await service.get_group_posts(group_id, user_id, limit, skip)
    return posts

# app/routes/group_routes.py - Thêm endpoint tìm kiếm

@router.get("/search", response_model=List[GroupResponse])
async def search_groups(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
    db = Depends(get_database)
):
    """Tìm kiếm nhóm theo tên hoặc mô tả"""
    service = GroupService(db)
    user_id = str(current_user.id) if current_user else None
    
    # Tìm kiếm nhóm công khai hoặc nhóm user đã tham gia
    pipeline = [
        {
            "$match": {
                "$or": [
                    {"name": {"$regex": keyword, "$options": "i"}},
                    {"description": {"$regex": keyword, "$options": "i"}}
                ],
                "is_active": True
            }
        },
        {"$limit": limit},
        {
            "$lookup": {
                "from": "users",
                "localField": "owner_id",
                "foreignField": "_id",
                "as": "owner_info"
            }
        },
        {
            "$unwind": {
                "path": "$owner_info",
                "preserveNullAndEmptyArrays": True
            }
        }
    ]
    
    groups = []
    cursor = service.collection.aggregate(pipeline)
    async for doc in cursor:
        # Chỉ hiển thị nhóm công khai hoặc nhóm user đã tham gia
        if doc["privacy"] == "public" or (user_id and any(m["user_id"] == user_id for m in doc.get("members", []))):
            doc["_id"] = str(doc["_id"])
            doc["owner_id"] = str(doc["owner_id"])
            doc["owner_name"] = doc.get("owner_info", {}).get("full_name") or doc.get("owner_info", {}).get("username")
            doc["owner_avatar"] = doc.get("owner_info", {}).get("avatar_url")
            
            if "owner_info" in doc:
                del doc["owner_info"]
            
            groups.append(doc)
    
    return groups