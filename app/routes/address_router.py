# app/routes/address_router.py
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.db.mongodb import get_database
from app.services.address_service import AddressService
from app.models.address_model import AddressCreate, AddressUpdate, AddressResponse
from app.core.security import get_current_user

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.post("/", response_model=AddressResponse, status_code=status.HTTP_201_CREATED)
async def create_address(
    address_in: AddressCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Tạo địa chỉ mới cho người dùng hiện tại"""
    service = AddressService(db)
    address_data = address_in.model_dump()
    
    # Kiểm tra nếu là địa chỉ đầu tiên, tự động đặt làm mặc định
    user_addresses = await service.get_user_addresses(str(current_user.id))
    if len(user_addresses) == 0:
        address_data["is_default"] = True
    
    return await service.create_address(str(current_user.id), address_data)


@router.get("/", response_model=List[AddressResponse])
async def get_my_addresses(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy tất cả địa chỉ của người dùng hiện tại"""
    service = AddressService(db)
    return await service.get_user_addresses(str(current_user.id))


@router.get("/default", response_model=AddressResponse)
async def get_default_address(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy địa chỉ mặc định"""
    service = AddressService(db)
    address = await service.get_default_address(str(current_user.id))
    if not address:
        raise HTTPException(status_code=404, detail="No default address found")
    return address


@router.get("/{address_id}", response_model=AddressResponse)
async def get_address(
    address_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy địa chỉ theo ID"""
    service = AddressService(db)
    address = await service.get_address_by_id(address_id, str(current_user.id))
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address


@router.put("/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: str,
    address_update: AddressUpdate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Cập nhật địa chỉ"""
    service = AddressService(db)
    address = await service.update_address(
        address_id,
        str(current_user.id),
        address_update.model_dump(exclude_unset=True)
    )
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    return address


@router.delete("/{address_id}")
async def delete_address(
    address_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Xóa địa chỉ"""
    service = AddressService(db)
    success = await service.delete_address(address_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Address not found")
    return {"message": "Address deleted successfully"}


@router.post("/{address_id}/set-default")
async def set_default_address(
    address_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Đặt địa chỉ làm mặc định"""
    service = AddressService(db)
    address = await service.set_default_address(address_id, str(current_user.id))
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Cập nhật default_address_id trong user collection
    user_collection = db["users"]
    await user_collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"default_address_id": address_id}}
    )
    
    return {"message": "Default address updated", "address": address}

# app/routes/user_routes.py (hoặc auth_routes.py)
@router.get("/me/default-address")
async def get_my_default_address(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    """Lấy địa chỉ mặc định của người dùng hiện tại"""
    address_service = AddressService(db)
    
    # Lấy default_address_id từ user
    default_address_id = current_user.get("default_address_id")
    
    if default_address_id:
        address = await address_service.get_address_by_id(default_address_id, str(current_user.id))
        if address:
            return address
    
    # Nếu không có, lấy địa chỉ đầu tiên hoặc None
    addresses = await address_service.get_user_addresses(str(current_user.id))
    if addresses:
        # Nếu có địa chỉ nhưng chưa có default, set default cho cái đầu
        if not default_address_id:
            await address_service.set_default_address(addresses[0]["id"], str(current_user.id))
        return addresses[0]
    
    return None