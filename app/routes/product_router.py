from fastapi import APIRouter, Depends, HTTPException, status
from app.db.mongodb import get_database
from app.models.products import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService
from app.core.security import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/", response_model=ProductResponse)
async def create_product(
    product_in: ProductCreate, # Tự động validate dữ liệu
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = ProductService(db)
    
    # Chuyển Model thành dict để xử lý
    product_data = product_in.model_dump()
    product_data["shop_id"] = str(current_user.id)
    
    return await service.create_product(product_data)


@router.get("/", response_model=list[ProductResponse])
async def get_products(
    db = Depends(get_database)
):

    service = ProductService(db)

    return await service.get_products()


@router.get("/{product_id}")
async def get_product(
    product_id: str,
    db = Depends(get_database)
):

    service = ProductService(db)

    return await service.get_product(product_id)


@router.put("/{product_id}")
async def update_product(
    product_id: str,
    product_update: ProductUpdate,
    db = Depends(get_database),
    current_user = Depends(get_current_user) # Bắt buộc đăng nhập
):
    service = ProductService(db)

    # 1. Lấy thông tin sản phẩm hiện tại
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")

    # 2. Ràng buộc quyền: Chỉ chủ shop hoặc Admin mới được sửa
    # (Giả định current_user có thuộc tính role, nếu không có bạn có thể bỏ phần check admin đi)
    is_admin = getattr(current_user, "role", "") == "admin"
    if product["shop_id"] != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền chỉnh sửa sản phẩm này")

    # 3. Thực hiện update
    data = product_update.model_dump(exclude_unset=True)
    return await service.update_product(product_id, data)


@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user) # Bắt buộc đăng nhập
):
    service = ProductService(db)

    # 1. Lấy thông tin sản phẩm hiện tại
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")

    # 2. Ràng buộc quyền: Chỉ chủ shop hoặc Admin mới được xóa
    is_admin = getattr(current_user, "role", "") == "admin"
    if product["shop_id"] != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa sản phẩm này")

    return await service.delete_product(product_id)

@router.get("/{product_id}/trace")
async def trace_product(
    product_id: str,
    db = Depends(get_database)
):

    service = ProductService(db)

    product = await service.get_product(product_id)

    return {
        "product_name": product["name"],
        "origin": product.get("origin"),
        "certification": product.get("certification"),
        "description": product.get("description"),
        "image": product.get("image_url")
    }