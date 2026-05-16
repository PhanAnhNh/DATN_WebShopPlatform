# app/services/group_service.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from pymongo import ReturnDocument

from app.models.group_model import GroupCreate, GroupMember, GroupPrivacy, GroupRole, GroupUpdate



class GroupService:
    def __init__(self, db):
        self.db = db
        self.collection = db["groups"]
        self.user_collection = db["users"]
        self.post_collection = db["social_posts"]

    async def create_group(self, group_data: GroupCreate, owner_id: str) -> Dict[str, Any]:
        """Tạo nhóm mới"""
        new_group = group_data.dict()
        new_group["owner_id"] = ObjectId(owner_id)
        new_group["members"] = [
            GroupMember(
                user_id=owner_id,
                role=GroupRole.ADMIN,
                joined_at=datetime.utcnow()
            ).dict()
        ]
        new_group["posts"] = []
        new_group["post_count"] = 0
        new_group["member_count"] = 1
        new_group["created_at"] = datetime.utcnow()
        new_group["is_active"] = True

        result = await self.collection.insert_one(new_group)
        group_id = str(result.inserted_id)

        return await self.get_group_by_id(group_id, owner_id)

    async def get_group_by_id(self, group_id: str, current_user_id: Optional[str] = None) -> Optional[Dict]:
        """Lấy thông tin nhóm theo ID"""
        try:
            pipeline = [
                {"$match": {"_id": ObjectId(group_id), "is_active": True}},
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

            cursor = self.collection.aggregate(pipeline)
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                doc["owner_id"] = str(doc["owner_id"])
                doc["owner_name"] = doc.get("owner_info", {}).get("full_name") or doc.get("owner_info", {}).get("username")
                doc["owner_avatar"] = doc.get("owner_info", {}).get("avatar_url")
                
                # Xác định vai trò của user hiện tại
                doc["user_role"] = None
                if current_user_id:
                    for member in doc.get("members", []):
                        if member["user_id"] == current_user_id:
                            doc["user_role"] = member["role"]
                            break
                
                if "owner_info" in doc:
                    del doc["owner_info"]
                
                return doc
            return None
        except Exception as e:
            print(f"Error getting group: {e}")
            return None

    async def get_my_groups(self, user_id: str) -> List[Dict]:
        """Lấy danh sách nhóm của user"""
        pipeline = [
            {"$match": {
                "members.user_id": user_id,
                "is_active": True
            }},
            {"$sort": {"created_at": -1}},
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
        cursor = self.collection.aggregate(pipeline)
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["owner_id"] = str(doc["owner_id"])
            doc["owner_name"] = doc.get("owner_info", {}).get("full_name") or doc.get("owner_info", {}).get("username")
            doc["owner_avatar"] = doc.get("owner_info", {}).get("avatar_url")
            
            # Vai trò của user
            for member in doc.get("members", []):
                if member["user_id"] == user_id:
                    doc["user_role"] = member["role"]
                    break
            
            if "owner_info" in doc:
                del doc["owner_info"]
            
            groups.append(doc)
        
        return groups

    async def get_public_groups(self, user_id: Optional[str] = None, limit: int = 20, skip: int = 0) -> List[Dict]:
        """Lấy danh sách nhóm công khai"""
        pipeline = [
            {"$match": {"privacy": GroupPrivacy.PUBLIC, "is_active": True}},
            {"$sort": {"member_count": -1, "created_at": -1}},
            {"$skip": skip},
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
        cursor = self.collection.aggregate(pipeline)
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["owner_id"] = str(doc["owner_id"])
            doc["owner_name"] = doc.get("owner_info", {}).get("full_name") or doc.get("owner_info", {}).get("username")
            doc["owner_avatar"] = doc.get("owner_info", {}).get("avatar_url")
            
            # Kiểm tra user đã tham gia chưa
            doc["user_role"] = None
            if user_id:
                for member in doc.get("members", []):
                    if member["user_id"] == user_id:
                        doc["user_role"] = member["role"]
                        break
            
            if "owner_info" in doc:
                del doc["owner_info"]
            
            groups.append(doc)
        
        return groups

    async def join_group(self, group_id: str, user_id: str) -> bool:
        """Tham gia nhóm"""
        group = await self.collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            return False

        # Kiểm tra đã là thành viên chưa
        for member in group.get("members", []):
            if member["user_id"] == user_id:
                return False

        # Nếu nhóm riêng tư, cần duyệt
        role = GroupRole.PENDING if group["privacy"] == GroupPrivacy.PRIVATE else GroupRole.MEMBER

        result = await self.collection.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$push": {
                    "members": {
                        "user_id": user_id,
                        "role": role,
                        "joined_at": datetime.utcnow()
                    }
                },
                "$inc": {"member_count": 1}
            }
        )
        
        return result.modified_count > 0

    async def leave_group(self, group_id: str, user_id: str) -> bool:
        """Rời nhóm"""
        group = await self.collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            return False

        # Không cho phép chủ nhóm rời nhóm
        if str(group["owner_id"]) == user_id:
            return False

        result = await self.collection.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$pull": {"members": {"user_id": user_id}},
                "$inc": {"member_count": -1}
            }
        )
        
        return result.modified_count > 0

    async def add_member(self, group_id: str, admin_id: str, user_id: str) -> bool:
        """Thêm thành viên (chỉ admin)"""
        group = await self.collection.find_one({
            "_id": ObjectId(group_id),
            "members": {
                "$elemMatch": {
                    "user_id": admin_id,
                    "role": GroupRole.ADMIN
                }
            }
        })
        
        if not group:
            return False

        # Kiểm tra đã là thành viên chưa
        for member in group.get("members", []):
            if member["user_id"] == user_id:
                return False

        result = await self.collection.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$push": {
                    "members": {
                        "user_id": user_id,
                        "role": GroupRole.MEMBER,
                        "joined_at": datetime.utcnow(),
                        "added_by": admin_id
                    }
                },
                "$inc": {"member_count": 1}
            }
        )
        
        return result.modified_count > 0

    async def remove_member(self, group_id: str, admin_id: str, user_id: str) -> bool:
        """Xóa thành viên (chỉ admin)"""
        group = await self.collection.find_one({
            "_id": ObjectId(group_id),
            "members": {
                "$elemMatch": {
                    "user_id": admin_id,
                    "role": GroupRole.ADMIN
                }
            }
        })
        
        if not group:
            return False

        # Không thể xóa chủ nhóm
        if str(group["owner_id"]) == user_id:
            return False

        result = await self.collection.update_one(
            {"_id": ObjectId(group_id)},
            {
                "$pull": {"members": {"user_id": user_id}},
                "$inc": {"member_count": -1}
            }
        )
        
        return result.modified_count > 0

    async def approve_member(self, group_id: str, admin_id: str, user_id: str) -> bool:
        """Duyệt thành viên (chỉ admin, cho nhóm riêng tư)"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(group_id),
                "members": {
                    "$elemMatch": {
                        "user_id": admin_id,
                        "role": GroupRole.ADMIN
                    }
                },
                "members.user_id": user_id,
                "members.role": GroupRole.PENDING
            },
            {
                "$set": {"members.$.role": GroupRole.MEMBER}
            }
        )
        
        return result.modified_count > 0

    async def update_group(self, group_id: str, user_id: str, update_data: GroupUpdate) -> Optional[Dict]:
        """Cập nhật nhóm (chỉ admin)"""
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        if not update_dict:
            return None

        update_dict["updated_at"] = datetime.utcnow()

        updated = await self.collection.find_one_and_update(
            {
                "_id": ObjectId(group_id),
                "members": {
                    "$elemMatch": {
                        "user_id": user_id,
                        "role": GroupRole.ADMIN
                    }
                }
            },
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER
        )

        if updated:
            updated["_id"] = str(updated["_id"])
            updated["owner_id"] = str(updated["owner_id"])
            return updated
        
        return None

    async def delete_group(self, group_id: str, user_id: str) -> bool:
        """Xóa nhóm (chỉ owner)"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(group_id),
                "owner_id": ObjectId(user_id)
            },
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0

    async def get_group_members(self, group_id: str, current_user_id: str, limit: int = 20, skip: int = 0) -> List[Dict]:
        """Lấy danh sách thành viên"""
        group = await self.collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            return []

        # Kiểm tra quyền xem (admin xem được tất cả, member xem được danh sách)
        is_admin = False
        is_member = False
        
        for member in group.get("members", []):
            if member["user_id"] == current_user_id:
                is_member = True
                if member["role"] == GroupRole.ADMIN:
                    is_admin = True
                break

        if not is_member and group["privacy"] == GroupPrivacy.PRIVATE:
            return []

        # Lấy danh sách user_id từ members
        member_ids = [m["user_id"] for m in group.get("members", [])]
        
        # Phân trang
        paginated_ids = member_ids[skip:skip + limit]
        
        # Lấy thông tin users
        users = []
        for user_id in paginated_ids:
            user = await self.user_collection.find_one({"_id": ObjectId(user_id)})
            if user:
                # Tìm role trong group
                role = None
                for m in group.get("members", []):
                    if m["user_id"] == user_id:
                        role = m["role"]
                        break
                
                users.append({
                    "_id": str(user["_id"]),
                    "full_name": user.get("full_name", user.get("username")),
                    "avatar_url": user.get("avatar_url"),
                    "role": role,
                    "joined_at": next((m["joined_at"] for m in group["members"] if m["user_id"] == user_id), None)
                })
        
        return users

    async def can_view_group_post(self, group_id: str, user_id: Optional[str], post_author_id: str) -> bool:
        """Kiểm tra user có thể xem bài viết trong nhóm không"""
        group = await self.collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            return False

        # Nhóm công khai: ai cũng xem được
        if group["privacy"] == GroupPrivacy.PUBLIC:
            return True

        # Nhóm riêng tư: chỉ thành viên mới xem được
        if user_id:
            for member in group.get("members", []):
                if member["user_id"] == user_id:
                    return True
        
        return False

    async def get_group_posts(self, group_id: str, current_user_id: Optional[str], limit: int = 10, skip: int = 0) -> List[Dict]:
        """Lấy bài viết trong nhóm"""
        # Kiểm tra quyền xem
        can_view = await self.can_view_group_post(group_id, current_user_id, None)
        if not can_view:
            return []

        pipeline = [
            {"$match": {
                "group_id": group_id,
                "is_active": True,
                "is_permanently_deleted": False
            }},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "author_id",
                    "foreignField": "_id",
                    "as": "author_info"
                }
            },
            {
                "$unwind": {
                    "path": "$author_info",
                    "preserveNullAndEmptyArrays": True
                }
            }
        ]

        posts = []
        cursor = self.post_collection.aggregate(pipeline)
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["author_id"] = str(doc["author_id"])
            doc["author_name"] = doc.get("author_info", {}).get("full_name") or doc.get("author_info", {}).get("username", "Người dùng")
            doc["author_avatar"] = doc.get("author_info", {}).get("avatar_url")
            
            if "author_info" in doc:
                del doc["author_info"]
            
            posts.append(doc)
        
        return posts