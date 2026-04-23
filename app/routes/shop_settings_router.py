# app/routes/shop_settings_router.py
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from app.db.mongodb import get_database
from app.core.security import get_current_user
from app.models.user_model import UserInDB
from app.services.shop_settings_service import ShopSettingsService
from typing import Any

router = APIRouter(prefix="/shop/settings", tags=["Shop Settings"])

def get_settings_service(db=Depends(get_database)):
    return ShopSettingsService(db)

@router.get("/")
async def get_settings(
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lấy toàn bộ cài đặt của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    settings = await service.get_settings(current_user.shop_id)
    return settings

@router.put("/general")
async def update_general_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt chung"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_general_settings(current_user.shop_id, data)

@router.put("/notifications")
async def update_notification_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt thông báo"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_notification_settings(current_user.shop_id, data)

@router.put("/payment")
async def update_payment_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt thanh toán"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_payment_settings(current_user.shop_id, data)

@router.put("/shipping")
async def update_shipping_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt vận chuyển"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_shipping_settings(current_user.shop_id, data)

@router.put("/security")
async def update_security_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt bảo mật"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_security_settings(current_user.shop_id, data)

@router.put("/invoice")
async def update_invoice_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt hóa đơn"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_invoice_settings(current_user.shop_id, data)

@router.put("/social")
async def update_social_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt mạng xã hội"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_social_settings(current_user.shop_id, data)

@router.put("/seo")
async def update_seo_settings(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật cài đặt SEO"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền thực hiện")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_seo_settings(current_user.shop_id, data)

# Thêm các endpoint mới vào cuối file shop_settings_router.py

@router.get("/payment/bank-accounts")
async def get_bank_accounts(
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lấy danh sách tài khoản ngân hàng của shop"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    settings = await service.get_settings(current_user.shop_id)
    return settings.get("payment", {}).get("bank_accounts", [])

@router.post("/payment/bank-accounts")
async def add_bank_account(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Thêm tài khoản ngân hàng mới"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.add_bank_account(current_user.shop_id, data)

@router.put("/payment/bank-accounts/{account_id}")
async def update_bank_account(
    account_id: str,
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Cập nhật tài khoản ngân hàng"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.update_bank_account(current_user.shop_id, account_id, data)

@router.delete("/payment/bank-accounts/{account_id}")
async def delete_bank_account(
    account_id: str,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Xóa tài khoản ngân hàng"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.delete_bank_account(current_user.shop_id, account_id)

@router.get("/public/{shop_id}")
async def get_public_shop_settings(
    shop_id: str,
    service: ShopSettingsService = Depends(get_settings_service)
):
    """
    Lấy cài đặt công khai của shop (không cần đăng nhập)
    Dùng cho trang thanh toán
    """
    try:
        settings = await service.get_settings(shop_id)
        
        # Chỉ trả về các thông tin cần thiết cho thanh toán
        public_settings = {
            "shop_id": settings.get("shop_id"),
            "shop_name": settings.get("general", {}).get("shop_name"),
            "payment": {
                "cod": settings.get("payment", {}).get("cod", True),
                "bank_transfer": settings.get("payment", {}).get("bank_transfer", True),
                "momo": settings.get("payment", {}).get("momo", False),
                "vnpay": settings.get("payment", {}).get("vnpay", False),
                "zalopay": settings.get("payment", {}).get("zalopay", False),
                "bank_accounts": [
                    {
                        "id": acc.get("id"),
                        "bank_name": acc.get("bank_name"),
                        "account_number": acc.get("account_number"),
                        "account_name": acc.get("account_name")
                    }
                    for acc in settings.get("payment", {}).get("bank_accounts", [])
                    if acc.get("is_active") is not False
                ]
            }
        }
        
        return public_settings
    except Exception as e:
        print(f"Error getting public settings: {e}")
        # Trả về cài đặt mặc định nếu có lỗi
        return {
            "shop_id": shop_id,
            "payment": {
                "cod": True,
                "bank_transfer": True,
                "momo": False,
                "vnpay": False,
                "zalopay": False,
                "bank_accounts": []
            }
        }

@router.post("/payment/upload-qr")
async def upload_qr_code(
    request: Request,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Upload QR code cho tài khoản ngân hàng"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    form = await request.form()
    account_id = form.get("account_id")
    file = form.get("file")
    
    if not file:
        raise HTTPException(status_code=400, detail="Không có file được upload")
    
    return await service.upload_qr_code(current_user.shop_id, account_id, file)

# Thêm vào cuối file app/routes/shop_settings_router.py

@router.get("/public/{shop_id}")
async def get_public_shop_settings(
    shop_id: str,
    db = Depends(get_database)
):
    """
    Lấy cài đặt công khai của shop (không cần đăng nhập)
    Dùng cho trang thanh toán
    """
    try:
        from app.services.shop_settings_service import ShopSettingsService
        service = ShopSettingsService(db)
        
        # Kiểm tra shop có tồn tại không
        shop = await db["shops"].find_one({"_id": ObjectId(shop_id)})
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        settings = await service.get_settings(shop_id)
        
        # Chỉ trả về các thông tin cần thiết cho thanh toán
        public_settings = {
            "shop_id": settings.get("shop_id"),
            "shop_name": settings.get("general", {}).get("shop_name", shop.get("name", "Cửa hàng")),
            "payment": {
                "cod": settings.get("payment", {}).get("cod", True),
                "bank_transfer": settings.get("payment", {}).get("bank_transfer", True),
                "momo": settings.get("payment", {}).get("momo", False),
                "vnpay": settings.get("payment", {}).get("vnpay", False),
                "zalopay": settings.get("payment", {}).get("zalopay", False),
                "bank_accounts": [
                    {
                        "id": acc.get("id"),
                        "bank_name": acc.get("bank_name"),
                        "bank_code": acc.get("bank_code"),
                        "account_number": acc.get("account_number"),
                        "account_name": acc.get("account_name"),
                        "branch": acc.get("branch"),
                        "qr_code_url": acc.get("qr_code_url"),
                        "is_active": acc.get("is_active", True)
                    }
                    for acc in settings.get("payment", {}).get("bank_accounts", [])
                    if acc.get("is_active") is not False
                ]
            }
        }
        
        return public_settings
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting public settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/payment/upload-qr")
async def upload_qr_code(
    account_id: str = Form(...),
    file: UploadFile = File(...),
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Upload QR code từ file lên Cloudflare R2"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    if not file:
        raise HTTPException(status_code=400, detail="Không có file được upload")
    
    return await service.upload_qr_code(current_user.shop_id, account_id, file)


@router.post("/payment/save-qr-url")
async def save_qr_url(
    data: dict,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Lưu URL QR code (nhập tay) cho tài khoản ngân hàng"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    account_id = data.get("account_id")
    qr_code_url = data.get("qr_code_url")
    
    if not account_id:
        raise HTTPException(status_code=400, detail="Thiếu account_id")
    
    if not qr_code_url:
        raise HTTPException(status_code=400, detail="Thiếu qr_code_url")
    
    return await service.save_qr_url(current_user.shop_id, account_id, qr_code_url)


@router.delete("/payment/delete-qr/{account_id}")
async def delete_qr_code(
    account_id: str,
    service: ShopSettingsService = Depends(get_settings_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Xóa QR code của tài khoản ngân hàng"""
    if current_user.role != "shop_owner":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
    
    if not current_user.shop_id:
        raise HTTPException(status_code=400, detail="Bạn chưa có shop")
    
    return await service.delete_qr_code(current_user.shop_id, account_id)