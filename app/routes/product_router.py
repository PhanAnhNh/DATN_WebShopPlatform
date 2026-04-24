# app/routes/product_router.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.db.mongodb import get_database
from app.models.products import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService
from app.core.security import get_current_user

router = APIRouter(prefix="/products", tags=["Products"])

@router.post("/", response_model=ProductResponse)
async def create_product(
    product_in: ProductCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = ProductService(db)
    product_data = product_in.model_dump()
    product_data["shop_id"] = str(current_user.id)
    return await service.create_product(product_data)

@router.get("/hot", response_model=list[ProductResponse])
async def get_hot_products(
    limit: int = Query(10, ge=1, le=50),
    db = Depends(get_database)
):
    """Lấy sản phẩm bán chạy"""
    service = ProductService(db)
    return await service.get_hot_products(limit=limit)

@router.get("/", response_model=list[ProductResponse])
async def get_products(
    sort: Optional[str] = Query(None, regex="^(hot|new|price_asc|price_desc)$"),
    db = Depends(get_database)
):
    service = ProductService(db)
    return await service.get_products(sort=sort)

# ⚠️ ĐỂ ROUTE NÀY Ở CUỐI CÙNG
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
    current_user = Depends(get_current_user)
):
    service = ProductService(db)

    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")

    is_admin = getattr(current_user, "role", "") == "admin"
    if product["shop_id"] != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền chỉnh sửa sản phẩm này")

    data = product_update.model_dump(exclude_unset=True)
    return await service.update_product(product_id, data)

@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = ProductService(db)

    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")

    is_admin = getattr(current_user, "role", "") == "admin"
    if product["shop_id"] != str(current_user.id) and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa sản phẩm này")

    return await service.delete_product(product_id)

@router.get("/{product_id}/trace")
async def trace_product(
    product_id: str,
    db = Depends(get_database)
):
    """Lấy thông tin truy xuất nguồn gốc đầy đủ"""
    from app.services.traceability_service import TraceabilityService
    
    product_service = ProductService(db)
    trace_service = TraceabilityService(db)
    
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    
    trace = await trace_service.get_traceability_by_product(product_id)
    
    stages = {
        "cultivation": {"name": "Nuôi trồng", "icon": "🌱", "events": []},
        "production": {"name": "Sản xuất", "icon": "🏭", "events": []},
        "processing": {"name": "Chế biến", "icon": "⚙️", "events": []},
        "transportation": {"name": "Vận chuyển", "icon": "🚚", "events": []},
        "distribution": {"name": "Phân phối", "icon": "🏪", "events": []},
        "certification": {"name": "Chứng nhận", "icon": "📜", "events": []}
    }
    
    if trace and trace.get("trace_events"):
        for event in trace["trace_events"]:
            stage = event.get("stage", "production")
            if stage in stages:
                stages[stage]["events"].append(event)
    
    return {
        "product": {
            "id": product["id"],
            "name": product["name"],
            "description": product.get("description"),
            "image_url": product.get("image_url"),
            "origin": product.get("origin"),
            "certification": product.get("certification"),
            "has_traceability": product.get("has_traceability", False)
        },
        "stages": stages,
        "trace_events": trace.get("trace_events", []) if trace else [],
        "qr_code_data": f"/product/{product_id}/trace" if trace else None
    }