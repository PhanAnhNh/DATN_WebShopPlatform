# app/routes/shops_router.py (hoặc shop_router.py tùy tên file)
from datetime import datetime
import math

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.core.security import get_current_user
from app.db.mongodb import get_database
from app.models.user_model import UserInDB
from app.services.distance_service import distance_service
from app.services.shop_service import ShopService
from app.services.product_service import ProductService
from app.models.shops_model import ShopCreate, ShopUpdate, ShopWithOwnerCreate
from app.models.products import ProductResponse

router = APIRouter(prefix="/shops", tags=["Shops"])


def get_shop_service(db=Depends(get_database)):
    return ShopService(db)

def get_product_service(db=Depends(get_database)):
    return ProductService(db)

@router.get("/info")
async def get_shop_info(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thông tin shop cho header và các component khác
    """
    # Kiểm tra quyền
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    # Lấy thông tin từ shops collection
    shop = await db["shops"].find_one({"_id": ObjectId(current_user.shop_id)})
    
    if not shop:
        raise HTTPException(status_code=404, detail="Không tìm thấy shop")
    
    # Lấy thông tin từ shop_settings để có dữ liệu cập nhật nhất
    settings = await db["shop_settings"].find_one({"shop_id": ObjectId(current_user.shop_id)})
    
    shop_name = settings.get("general", {}).get("shop_name") if settings else None
    shop_email = settings.get("general", {}).get("shop_email") if settings else None
    shop_phone = settings.get("general", {}).get("shop_phone") if settings else None
    shop_address = settings.get("general", {}).get("shop_address") if settings else None
    
    return {
        "id": str(shop["_id"]),
        "name": shop_name or shop.get("name", ""),
        "email": shop_email or shop.get("email", ""),
        "phone": shop_phone or shop.get("phone", ""),
        "address": shop_address or shop.get("address", ""),
        "logo_url": shop.get("logo_url"),
        "banner_url": shop.get("banner_url"),
        "is_verified": shop.get("is_verified", False),
        "followers_count": shop.get("followers_count", 0),
        "general_settings": settings.get("general") if settings else None
    }

@router.get("/stats")
async def get_shops_stats(
    db = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Lấy thống kê tổng quan các shop (chỉ admin)
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    total_shops = await db["shops"].count_documents({})
    active_shops = await db["shops"].count_documents({"status": "active"})
    verified_shops = await db["shops"].count_documents({"is_verified": True})
    
    return {
        "total": total_shops,
        "active": active_shops,
        "verified": verified_shops
    }

@router.get("/")
async def list_shops(
    skip: int = 0,
    limit: int = 20,
    service: ShopService = Depends(get_shop_service)
):
    return await service.list_shops(skip, limit)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_shop(
    shop_in: ShopCreate,
    service: ShopService = Depends(get_shop_service),
    current_user=Depends(get_current_user)
):
    # Chuyển dữ liệu model thành dict và tự động gán owner_id từ user đang đăng nhập
    shop_data = shop_in.model_dump()
    shop_data["owner_id"] = str(current_user.id)
    
    return await service.create_shop(shop_data, shop_data)  # Sửa lại tham số

@router.post("/with-owner", status_code=status.HTTP_201_CREATED)
async def create_shop_with_owner(
    data: ShopWithOwnerCreate,
    service: ShopService = Depends(get_shop_service)
):
    """
    Tạo cửa hàng mới kèm tài khoản chủ shop
    """
    result, error = await service.create_shop_with_owner(data.model_dump())
    
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    return {
        "message": "Tạo cửa hàng và tài khoản chủ shop thành công",
        "data": result
    }

# app/routes/shops_router.py - SỬA LẠI hàm get_nearby_shops

@router.get("/nearby")
async def get_nearby_shops(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(10),
    limit: int = Query(20),
    db = Depends(get_database)
):
    shops_collection = db["shops"]
    locations_collection = db["locations"]
    
    shops = []
    cursor = shops_collection.find({"status": "active"})
    
    shop_service = ShopService(db)
    
    async for shop in cursor:
        location_id = shop.get("location_id")
        if not location_id:
            continue
        
        if isinstance(location_id, ObjectId):
            location_obj_id = location_id
        else:
            try:
                location_obj_id = ObjectId(location_id)
            except:
                continue
        
        location = await locations_collection.find_one({"_id": location_obj_id})
        if not location:
            continue
        
        shop_lat = location.get("lat")
        shop_lng = location.get("lng")
        
        if shop_lat is None or shop_lng is None:
            continue
        
        # ✅ Dùng API đường đi thay vì Haversine
        road_distance = await distance_service.get_road_distance(lat, lng, shop_lat, shop_lng)
        
        if road_distance and road_distance["distance_km"] <= radius_km:
            shop = shop_service._convert_objectids(shop)
            shop["distance_km"] = road_distance["distance_km"]
            shop["duration_min"] = road_distance["duration_min"]
            shops.append(shop)
        elif not road_distance:
            # Fallback to Haversine nếu API lỗi
            distance = calculate_distance(lat, lng, shop_lat, shop_lng) * 1.3
            if distance <= radius_km:
                shop = shop_service._convert_objectids(shop)
                shop["distance_km"] = distance
                shop["duration_min"] = round(distance * 2, 1)  # Ước lượng 2 phút/km
                shops.append(shop)
    
    shops.sort(key=lambda x: x["distance_km"])
    
    return {
        "data": shops[:limit],
        "user_location": {"lat": lat, "lng": lng},
        "total": len(shops[:limit])
    }

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Tính khoảng cách Haversine (km)"""
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return round(R * c, 2)

@router.get("/{shop_id}")
async def get_shop(shop_id: str, service: ShopService = Depends(get_shop_service)):
    shop = await service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Tăng view_count
    await service.increment_shop_view(shop_id)
    
    return shop

@router.get("/{shop_id}/products", response_model=list[ProductResponse])
async def get_shop_products(
    shop_id: str,
    skip: int = 0,
    limit: int = 20,
    product_service: ProductService = Depends(get_product_service)
):
    """
    Lấy danh sách sản phẩm của shop
    """
    # Kiểm tra shop có tồn tại không
    shop_service = ShopService(product_service.db)
    shop = await shop_service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Lấy sản phẩm của shop
    products = []
    cursor = product_service.collection.find({"shop_id": ObjectId(shop_id)}).skip(skip).limit(limit)
    
    async for doc in cursor:
        product_id = str(doc["_id"])
        
        # Chuyển đổi ObjectId sang string
        doc["id"] = product_id
        doc["_id"] = product_id
        doc["shop_id"] = str(doc["shop_id"])
        if "category_id" in doc:
            doc["category_id"] = str(doc["category_id"])
        
        # Lấy variants cho sản phẩm này
        variants = []
        variant_cursor = product_service.variant_collection.find({"product_id": ObjectId(product_id)})
        async for v in variant_cursor:
            v["id"] = str(v["_id"])
            v["_id"] = str(v["_id"])
            v["product_id"] = str(v["product_id"])
            variants.append(v)
        
        doc["variants"] = variants
        
        # Nếu có variants, tính lại price và stock từ variants
        if variants:
            doc["price"] = min(v["price"] for v in variants)
            doc["stock"] = sum(v["stock"] for v in variants)
        
        products.append(doc)
    
    return products

@router.get("/{shop_id}/reviews")
async def get_shop_reviews(
    shop_id: str,
    skip: int = 0,
    limit: int = 20,
    db = Depends(get_database)
):
    """
    Lấy danh sách đánh giá của shop
    """
    # Kiểm tra shop có tồn tại không
    shop_service = ShopService(db)
    shop = await shop_service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    reviews_collection = db["reviews"]
    
    reviews = []
    cursor = reviews_collection.find({"shop_id": ObjectId(shop_id)}).skip(skip).limit(limit)
    
    async for review in cursor:
        review["id"] = str(review["_id"])
        review["_id"] = str(review["_id"])
        review["shop_id"] = str(review["shop_id"])
        if "user_id" in review:
            review["user_id"] = str(review["user_id"])
        reviews.append(review)
    
    return reviews

@router.post("/{shop_id}/reviews", status_code=status.HTTP_201_CREATED)
async def create_shop_review(
    shop_id: str,
    review_data: dict,
    db = Depends(get_database),
    current_user=Depends(get_current_user)
):
    """
    Tạo đánh giá cho shop
    """
    # Kiểm tra shop có tồn tại không
    shop_service = ShopService(db)
    shop = await shop_service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Tạo review
    reviews_collection = db["reviews"]
    
    review = {
        "shop_id": ObjectId(shop_id),
        "user_id": ObjectId(current_user.id),
        "user_name": getattr(current_user, "full_name", current_user.username),
        "user_avatar": getattr(current_user, "avatar_url", None),
        "rating": review_data.get("rating", 5),
        "comment": review_data.get("comment", ""),
        "created_at": datetime.utcnow()
    }
    
    result = await reviews_collection.insert_one(review)
    
    # Cập nhật lại số lượng đánh giá và rating trung bình cho shop
    # Tính rating trung bình
    pipeline = [
        {"$match": {"shop_id": ObjectId(shop_id)}},
        {"$group": {
            "_id": None,
            "avg_rating": {"$avg": "$rating"},
            "total_reviews": {"$sum": 1}
        }}
    ]
    
    cursor = reviews_collection.aggregate(pipeline)
    stats = await cursor.to_list(length=1)
    
    if stats:
        avg_rating = stats[0]["avg_rating"]
        total_reviews = stats[0]["total_reviews"]
        
        await shop_service.collection.update_one(
            {"_id": ObjectId(shop_id)},
            {"$set": {
                "rating": round(avg_rating, 1),
                "total_reviews": total_reviews,
                "updated_at": datetime.utcnow()
            }}
        )
    
    # Trả về review vừa tạo
    created_review = await reviews_collection.find_one({"_id": result.inserted_id})
    created_review["id"] = str(created_review["_id"])
    created_review["_id"] = str(created_review["_id"])
    created_review["shop_id"] = str(created_review["shop_id"])
    created_review["user_id"] = str(created_review["user_id"])
    
    return created_review

@router.post("/{shop_id}/follow")
async def follow_shop(
    shop_id: str,
    db = Depends(get_database),
    current_user=Depends(get_current_user)
):
    """
    Theo dõi shop
    """
    # Kiểm tra shop có tồn tại không
    shop_service = ShopService(db)
    shop = await shop_service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Kiểm tra đã follow chưa
    follows_collection = db["shop_follows"]
    existing = await follows_collection.find_one({
        "user_id": ObjectId(current_user.id),
        "shop_id": ObjectId(shop_id)
    })
    
    if existing:
        # Nếu đã follow thì unfollow
        await follows_collection.delete_one({"_id": existing["_id"]})
        # Giảm số lượng followers
        await shop_service.collection.update_one(
            {"_id": ObjectId(shop_id)},
            {"$inc": {"followers_count": -1}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return {"message": "Unfollowed shop", "following": False}
    else:
        # Nếu chưa follow thì follow
        follow = {
            "user_id": ObjectId(current_user.id),
            "shop_id": ObjectId(shop_id),
            "created_at": datetime.utcnow()
        }
        await follows_collection.insert_one(follow)
        # Tăng số lượng followers
        await shop_service.collection.update_one(
            {"_id": ObjectId(shop_id)},
            {"$inc": {"followers_count": 1}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return {"message": "Followed shop", "following": True}

@router.put("/{shop_id}")
async def update_shop(
    shop_id: str,
    shop_in: ShopUpdate,
    service: ShopService = Depends(get_shop_service),
    current_user=Depends(get_current_user)
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

@router.get("/{shop_id}/dashboard")
async def shop_dashboard(
    shop_id: str, 
    service: ShopService = Depends(get_shop_service),
    current_user=Depends(get_current_user)
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

@router.get("/{shop_id}/follow-status")
async def get_follow_status(
    shop_id: str,
    db = Depends(get_database),
    current_user=Depends(get_current_user)
):
    """
    Kiểm tra xem user hiện tại đã follow shop chưa
    """
    # Kiểm tra shop có tồn tại không
    shop_service = ShopService(db)
    shop = await shop_service.get_shop_by_id(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Kiểm tra trạng thái follow
    follows_collection = db["shop_follows"]
    existing = await follows_collection.find_one({
        "user_id": ObjectId(current_user.id),
        "shop_id": ObjectId(shop_id)
    })
    
    return {"isFollowing": existing is not None}

@router.get("/{shop_id}/payment-info")
async def get_shop_payment_info(
    shop_id: str,
    db = Depends(get_database)
):
    """
    Lấy thông tin thanh toán của shop (tài khoản ngân hàng, QR code)
    Dùng cho trang thanh toán sau khi đặt hàng
    """
    # Lấy thông tin shop
    shop = await db["shops"].find_one({"_id": ObjectId(shop_id)})
    if not shop:
        raise HTTPException(status_code=404, detail="Shop not found")
    
    # Lấy thông tin thanh toán từ shop_settings
    settings = await db["shop_settings"].find_one({"shop_id": ObjectId(shop_id)})
    
    # Thông tin ngân hàng mặc định (có thể lấy từ settings hoặc từ shop)
    payment_info = {
        "shop_id": str(shop["_id"]),
        "shop_name": shop.get("name", ""),
        "bank_info": {
            "bank_name": "Vietcombank",
            "bank_code": "VCB",
            "account_number": "123456789",
            "account_name": shop.get("name", "CỬA HÀNG"),
            "branch": "Chi nhánh Hà Nội"
        }
    }
    
    # Nếu có settings, ghi đè
    if settings and settings.get("payment_settings"):
        payment_settings = settings.get("payment_settings", {})
        if payment_settings.get("bank_info"):
            payment_info["bank_info"] = payment_settings["bank_info"]
    
    # Tạo QR code URL nếu có
    if payment_info["bank_info"].get("account_number"):
        # Có thể generate QR code động ở đây
        payment_info["qr_code_url"] = f"/static/qr/shop_{shop_id}.png"
    
    return payment_info
