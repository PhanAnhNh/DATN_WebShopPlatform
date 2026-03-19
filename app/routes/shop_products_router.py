from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.models.products import ProductCreate, ProductUpdate, ProductResponse
from app.services.product_service import ProductService
from bson import ObjectId
from typing import Optional, List
import os
import shutil
from datetime import datetime, timedelta

router = APIRouter(prefix="/shop/products", tags=["Shop Products"])

# app/routes/shop_products_router.py

@router.get("/")
async def get_shop_products(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    category_id: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Lấy danh sách sản phẩm của shop (phân trang, tìm kiếm, lọc)
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy shop_id
    shop_id = current_user.shop_id
    if not shop_id and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Build query
    query = {}
    if current_user.role != "admin":
        query["shop_id"] = ObjectId(shop_id)
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    
    if category_id:
        query["category_id"] = ObjectId(category_id)
    
    if status == "in_stock":
        query["stock"] = {"$gt": 0}
    elif status == "out_of_stock":
        query["stock"] = 0
    
    # Tính skip
    skip = (page - 1) * limit
    
    # Lấy tổng số
    total = await db["products"].count_documents(query)
    
    # Lấy danh sách sản phẩm
    cursor = db["products"].find(query).sort("created_at", -1).skip(skip).limit(limit)
    products = await cursor.to_list(length=limit)
    
    # Format response
    result = []
    for product in products:
        # Lấy variants
        variants = await db["product_variants"].find(
            {"product_id": product["_id"]}
        ).to_list(length=None)
        
        # Tính tổng stock
        total_stock = product.get("stock", 0)
        if variants:
            total_stock = sum(v.get("stock", 0) for v in variants)
        
        # Xác định giá hiển thị
        display_price = product.get("price", 0)
        if variants and len(variants) > 0:
            # Nếu có variants, lấy giá thấp nhất (hoặc giá đầu tiên)
            # Có thể chọn logic: giá thấp nhất, giá trung bình, hoặc khoảng giá
            min_price = min(v.get("price", 0) for v in variants)
            max_price = max(v.get("price", 0) for v in variants)
            
            if min_price == max_price:
                display_price = min_price
            else:
                # Hiển thị khoảng giá, ví dụ: "20,000đ - 50,000đ"
                # Nhưng trong table chỉ hiển thị 1 giá, nên dùng min_price
                display_price = min_price
                
                # Nếu muốn hiển thị khoảng giá, có thể thêm field price_range
                # product["price_range"] = f"{min_price} - {max_price}"
        
        result.append({
            "id": str(product["_id"]),
            "name": product["name"],
            "description": product.get("description"),
            "price": display_price,  # Dùng price đã xử lý
            "stock": total_stock,
            "category_id": str(product["category_id"]),
            "image_url": product.get("image_url"),
            "status": "in_stock" if total_stock > 0 else "out_of_stock",
            "created_at": product["created_at"],
            "variants_count": len(variants)
        })
    
    return {
        "data": result,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@router.post("/", response_model=ProductResponse)
async def create_shop_product(
    product_in: ProductCreate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Tạo sản phẩm mới cho shop
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Lấy shop_id
    shop_id = current_user.shop_id
    if not shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Log dữ liệu nhận được
    print(f"Received product data: {product_in.dict()}")
    
    service = ProductService(db)
    product_data = product_in.dict()
    product_data["shop_id"] = shop_id
    
    # Tạo sản phẩm
    product = await service.create_product(product_data)
    
    # Đảm bảo tất cả ID đều là string
    if "category_id" in product and isinstance(product["category_id"], ObjectId):
        product["category_id"] = str(product["category_id"])
    if "shop_id" in product and isinstance(product["shop_id"], ObjectId):
        product["shop_id"] = str(product["shop_id"])
    
    return product

@router.get("/{product_id}")
async def get_shop_product_detail(
    product_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xem chi tiết sản phẩm
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    # Lấy sản phẩm
    product = await db["products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    
    # Kiểm tra quyền sở hữu
    if current_user.role != "admin" and str(product["shop_id"]) != current_user.shop_id:
        raise HTTPException(status_code=403, detail="Không có quyền xem sản phẩm này")
    
    # Lấy variants
    variants = await db["product_variants"].find(
        {"product_id": ObjectId(product_id)}
    ).to_list(length=None)
    
    # Lấy category
    category = await db["categories"].find_one({"_id": product["category_id"]})
    
    # Format variants
    formatted_variants = []
    for v in variants:
        formatted_variants.append({
            "id": str(v["_id"]),
            "name": v["name"],
            "price": v["price"],
            "stock": v["stock"],
            "sku": v.get("sku"),
            "image_url": v.get("image_url")
        })
    
    return {
        "id": str(product["_id"]),
        "name": product["name"],
        "description": product.get("description"),
        "price": product.get("price"),
        "stock": product.get("stock", 0),
        "category": {
            "id": str(category["_id"]) if category else None,
            "name": category["name"] if category else None
        },
        "origin": product.get("origin"),
        "certification": product.get("certification"),
        "image_url": product.get("image_url"),
        "qr_code_url": product.get("qr_code_url"),
        "variants": formatted_variants,
        "created_at": product["created_at"],
        "updated_at": product.get("updated_at")
    }

@router.put("/{product_id}")
async def update_shop_product(
    product_id: str,
    product_update: ProductUpdate,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Cập nhật sản phẩm
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Kiểm tra sản phẩm tồn tại
    product = await db["products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    
    # Kiểm tra quyền sở hữu
    if current_user.role != "admin" and str(product["shop_id"]) != current_user.shop_id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa sản phẩm này")
    
    service = ProductService(db)
    update_data = product_update.model_dump(exclude_unset=True)
    
    return await service.update_product(product_id, update_data)

@router.delete("/{product_id}")
async def delete_shop_product(
    product_id: str,
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Xóa sản phẩm
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Kiểm tra sản phẩm tồn tại
    product = await db["products"].find_one({"_id": ObjectId(product_id)})
    if not product:
        raise HTTPException(status_code=404, detail="Không tìm thấy sản phẩm")
    
    # Kiểm tra quyền sở hữu
    if current_user.role != "admin" and str(product["shop_id"]) != current_user.shop_id:
        raise HTTPException(status_code=403, detail="Không có quyền xóa sản phẩm này")
    
    # Xóa variants trước
    await db["product_variants"].delete_many({"product_id": ObjectId(product_id)})
    
    # Xóa sản phẩm
    await db["products"].delete_one({"_id": ObjectId(product_id)})
    
    return {"message": "Xóa sản phẩm thành công"}

@router.post("/{product_id}/upload-image")
async def upload_product_image(
    product_id: str,
    file: UploadFile = File(...),
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Upload ảnh cho sản phẩm
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    # Kiểm tra file
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File phải là ảnh")
    
    # Tạo thư mục nếu chưa có
    upload_dir = "static/product_images"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Tạo tên file
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{product_id}_{datetime.now().timestamp()}{file_ext}"
    file_path = os.path.join(upload_dir, file_name)
    
    # Lưu file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Cập nhật database
    image_url = f"/static/product_images/{file_name}"
    await db["products"].update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"image_url": image_url}}
    )
    
    return {"image_url": image_url}

@router.get("/stats/overview")
async def get_shop_products_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê sản phẩm cho dashboard
    """
    if current_user.role not in ["shop_owner", "admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    shop_id = current_user.shop_id
    
    # Tổng số sản phẩm
    total_products = await db["products"].count_documents(
        {"shop_id": ObjectId(shop_id)} if shop_id else {}
    )
    
    # Sản phẩm còn hàng
    in_stock = await db["products"].count_documents({
        "shop_id": ObjectId(shop_id),
        "stock": {"$gt": 0}
    } if shop_id else {"stock": {"$gt": 0}})
    
    # Sản phẩm hết hàng
    out_of_stock = await db["products"].count_documents({
        "shop_id": ObjectId(shop_id),
        "stock": 0
    } if shop_id else {"stock": 0})
    
    # Sản phẩm mới trong 7 ngày
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_products = await db["products"].count_documents({
        "shop_id": ObjectId(shop_id),
        "created_at": {"$gte": week_ago}
    } if shop_id else {"created_at": {"$gte": week_ago}})
    
    return {
        "total_products": total_products,
        "in_stock": in_stock,
        "out_of_stock": out_of_stock,
        "new_products": new_products
    }