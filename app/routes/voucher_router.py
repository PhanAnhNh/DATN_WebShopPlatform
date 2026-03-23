from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from app.services.voucher_service import VoucherService
from app.core.security import CurrentUser, get_current_user
from app.db.mongodb import get_database
from dateutil import parser

router = APIRouter(prefix="/vouchers", tags=["Vouchers"])

@router.post("/")
async def create_voucher(
    data: dict,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = VoucherService(db)

    return await service.create_voucher(data)

@router.get("/")
async def get_vouchers(
    db = Depends(get_database)
):

    service = VoucherService(db)

    return await service.get_vouchers()

@router.post("/save/{voucher_id}")
async def save_voucher(
    voucher_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = VoucherService(db)

    return await service.save_voucher(
        str(current_user.id),
        voucher_id
    )

# app/routes/voucher_router.py
# app/routes/voucher_router.py
@router.post("/validate")
async def validate_voucher(
    code: str,
    order_total: float,
    shop_id: str = None,
    db = Depends(get_database),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = VoucherService(db)
    
    # Debug: In ra để kiểm tra
    print(f"=== VALIDATE VOUCHER ENDPOINT ===")
    print(f"Code: {code}")
    print(f"Order total: {order_total}")
    print(f"Shop ID: {shop_id}")
    print(f"User ID: {current_user.id}")
    
    return await service.validate_voucher(
        code, 
        order_total, 
        user_id=str(current_user.id),
        shop_id=shop_id
    )

@router.post("/{voucher_id}/use")
async def use_voucher(
    voucher_id: str,
    db = Depends(get_database)
):
    service = VoucherService(db)
    return await service.increase_usage(voucher_id)

@router.get("/my-vouchers")
async def get_my_vouchers(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = VoucherService(db)
    return await service.get_user_vouchers(str(current_user.id))

# app/routes/voucher_router.py
@router.get("/available")
async def get_available_vouchers(
    db = Depends(get_database),
    current_user: CurrentUser = Depends(get_current_user),
    shop_id: str = None,
    order_total: float = 0
):
    """
    Lấy danh sách voucher phù hợp với user và order
    """
    service = VoucherService(db)
    
    # Lấy tất cả voucher active
    vouchers = await service.get_vouchers()
    
    # Lọc voucher phù hợp
    available_vouchers = []
    for v in vouchers:
        # Kiểm tra target_type
        if v["target_type"] == "shop" and shop_id and v.get("shop_id") != shop_id:
            continue
        
        # Kiểm tra ngày hết hạn
        end_date = v["end_date"]
        if isinstance(end_date, str):
            end_date = parser.parse(end_date)
            end_date = end_date.astimezone(timezone.utc).replace(tzinfo=None)
        
        if end_date < datetime.utcnow():
            continue
        
        # Kiểm tra số lần sử dụng
        if v.get("usage_limit") and v["used_count"] >= v["usage_limit"]:
            continue
        
        # Kiểm tra đơn hàng tối thiểu
        if order_total < v["min_order_value"]:
            continue
        
        available_vouchers.append(v)
    
    return available_vouchers