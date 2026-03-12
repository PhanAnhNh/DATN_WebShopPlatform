from fastapi import APIRouter, Depends
from app.services.voucher_service import VoucherService
from app.core.security import get_current_user
from app.db.mongodb import get_database

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

@router.post("/validate")
async def validate_voucher(
    code: str,
    order_total: float,
    db = Depends(get_database)
):

    service = VoucherService(db)

    return await service.validate_voucher(code, order_total)

