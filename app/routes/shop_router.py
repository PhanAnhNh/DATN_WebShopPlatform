from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.db.mongodb import get_database
from app.services.shop_service import ShopService
from app.models.shops_model import ShopCreate, ShopUpdate

router = APIRouter(prefix="/shops", tags=["Shops"])


def get_shop_service(db = Depends(get_database)):
    return ShopService(db)

# =========================
# CREATE SHOP
# =========================
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_shop(
    shop_in: ShopCreate,
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user) # Bắt buộc đăng nhập
):
    # Chuyển dữ liệu model thành dict và tự động gán owner_id từ user đang đăng nhập
    shop_data = shop_in.model_dump()
    shop_data["owner_id"] = str(current_user.id)
    
    # Bạn sẽ cần sửa nhẹ hàm create_shop trong service để nhận dict thay vì model
    return await service.create_shop(shop_data)

@router.get("/{shop_id}")
async def get_shop(shop_id: str, service: ShopService = Depends(get_shop_service)):
    shop = await service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop

@router.put("/{shop_id}")
async def update_shop(
    shop_id: str,
    shop_in: ShopUpdate,
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user) # Bắt buộc đăng nhập
):
    # 1. Kiểm tra shop có tồn tại không
    existing_shop = await service.get_shop_by_id(shop_id)
    if not existing_shop:
        raise HTTPException(status_code=404, detail="Shop not found")
        
    # 2. Ràng buộc quyền: Chỉ chủ shop (hoặc Admin) mới được sửa
    is_admin = getattr(current_user, "role", "") == "admin"
    if existing_shop.get("owner_id") != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=403, detail="Không có quyền chỉnh sửa shop này")

    return await service.update_shop(shop_id, shop_in)

@router.get("/")
async def list_shops(
    skip: int = 0,
    limit: int = 20,
    service: ShopService = Depends(get_shop_service)
):
    return await service.list_shops(skip, limit)

@router.get("/{shop_id}/dashboard")
async def shop_dashboard(
    shop_id: str, 
    service: ShopService = Depends(get_shop_service),
    current_user = Depends(get_current_user) # Bắt buộc đăng nhập
):
    # 1. Lấy thông tin shop
    existing_shop = await service.get_shop_by_id(shop_id)
    if not existing_shop:
        raise HTTPException(status_code=404, detail="Shop not found")
        
    # 2. Ràng buộc quyền: Dashboard chứa doanh thu, CHỈ chủ shop/admin được xem
    is_admin = getattr(current_user, "role", "") == "admin"
    if existing_shop.get("owner_id") != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=403, detail="Không có quyền xem báo cáo của shop này")

    return await service.get_shop_dashboard(shop_id)