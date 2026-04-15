# app/api/v1/endpoints/traceability.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.db.mongodb import get_database
from app.services.traceability_service import TraceabilityService
from app.services.product_service import ProductService
from app.core.security import get_current_user, get_current_shop_owner
from app.models.product_traceability import TraceabilityCreate, TraceEvent

router = APIRouter(prefix="/traceability", tags=["Traceability"])

@router.post("/products/{product_id}")
async def create_traceability(
    product_id: str,
    trace_data: TraceabilityCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_shop_owner)
):
    """Tạo truy xuất nguồn gốc cho sản phẩm (chỉ shop owner)"""
    product_service = ProductService(db)
    trace_service = TraceabilityService(db)
    
    # Kiểm tra sản phẩm tồn tại và thuộc shop
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    
    if product["shop_id"] != str(current_user.shop_id):
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    # Kiểm tra đã có traceability chưa
    existing = await trace_service.get_traceability_by_product(product_id)
    if existing:
        raise HTTPException(status_code=400, detail="Sản phẩm đã có truy xuất nguồn gốc")
    
    result = await trace_service.create_traceability(product_id, trace_data.dict())
    return result

@router.get("/products/{product_id}")
async def get_traceability(
    product_id: str,
    db = Depends(get_database)
):
    """Lấy truy xuất nguồn gốc của sản phẩm (công khai)"""
    trace_service = TraceabilityService(db)
    product_service = ProductService(db)
    
    # Kiểm tra sản phẩm tồn tại
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")
    
    trace = await trace_service.get_traceability_by_product(product_id)
    if not trace:
        # Trả về thông tin cơ bản nếu chưa có traceability
        return {
            "product_id": product_id,
            "product_name": product["name"],
            "has_traceability": False,
            "origin": product.get("origin"),
            "certification": product.get("certification"),
            "message": "Sản phẩm chưa có thông tin truy xuất nguồn gốc chi tiết"
        }
    
    # Thêm thông tin sản phẩm vào response
    trace["product_name"] = product["name"]
    trace["product_image"] = product.get("image_url")
    trace["origin"] = product.get("origin")
    trace["certification"] = product.get("certification")
    
    return trace

@router.post("/products/{product_id}/events")
async def add_trace_event(
    product_id: str,
    event: TraceEvent,
    db = Depends(get_database),
    current_user = Depends(get_current_shop_owner)
):
    """Thêm event mới vào traceability"""
    trace_service = TraceabilityService(db)
    product_service = ProductService(db)
    
    product = await product_service.get_product(product_id)
    if not product or product["shop_id"] != str(current_user.shop_id):
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    result = await trace_service.add_trace_event(product_id, event.dict())
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy traceability")
    
    return {"message": "Đã thêm event thành công"}

@router.put("/products/{product_id}/events/{event_index}")
async def update_trace_event(
    product_id: str,
    event_index: int,
    event: TraceEvent,
    db = Depends(get_database),
    current_user = Depends(get_current_shop_owner)
):
    """Cập nhật event"""
    trace_service = TraceabilityService(db)
    product_service = ProductService(db)
    
    product = await product_service.get_product(product_id)
    if not product or product["shop_id"] != str(current_user.shop_id):
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    result = await trace_service.update_trace_event(product_id, event_index, event.dict())
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy event")
    
    return {"message": "Cập nhật event thành công"}

@router.delete("/products/{product_id}/events/{event_index}")
async def delete_trace_event(
    product_id: str,
    event_index: int,
    db = Depends(get_database),
    current_user = Depends(get_current_shop_owner)
):
    """Xóa event"""
    trace_service = TraceabilityService(db)
    product_service = ProductService(db)
    
    product = await product_service.get_product(product_id)
    if not product or product["shop_id"] != str(current_user.shop_id):
        raise HTTPException(status_code=403, detail="Không có quyền")
    
    result = await trace_service.delete_trace_event(product_id, event_index)
    if not result:
        raise HTTPException(status_code=404, detail="Không tìm thấy event")
    
    return {"message": "Xóa event thành công"}