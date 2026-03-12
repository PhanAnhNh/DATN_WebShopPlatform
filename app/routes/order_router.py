from fastapi import APIRouter, Depends, HTTPException
from app.db.mongodb import get_database
from app.services.order_service import OrderService
from app.models.orders_model import OrderCreate, OrderStatus
from app.core.security import get_current_user

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/")
async def create_order(
    order: OrderCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = OrderService(db)

    return await service.create_order(
        str(current_user.id),
        order.dict()
    )


@router.get("/my")
async def my_orders(
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = OrderService(db)

    return await service.get_user_orders(
        str(current_user.id)
    )


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    db = Depends(get_database)
):

    service = OrderService(db)

    order = await service.get_order(order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@router.put("/{order_id}/status")
async def update_status(
    order_id: str,
    status: OrderStatus,
    db = Depends(get_database)
):

    service = OrderService(db)

    return await service.update_order_status(order_id, status)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):
    service = OrderService(db)
    try:
        return await service.cancel_order(order_id, str(current_user.id))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    