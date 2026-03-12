from fastapi import APIRouter, Depends
from app.db.mongodb import get_database

from app.models.category_model import CategoryCreate
from app.services.category_service import CategoryService

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)


@router.post("/")
async def create_category(
    category_in: CategoryCreate,
    db = Depends(get_database)
):

    service = CategoryService(db)

    data = category_in.model_dump()

    return await service.create_category(data)


@router.get("/")
async def get_categories(
    db = Depends(get_database)
):

    service = CategoryService(db)

    return await service.get_categories()


@router.get("/{category_id}")
async def get_category(
    category_id: str,
    db = Depends(get_database)
):

    service = CategoryService(db)

    return await service.get_category(category_id)


@router.put("/{category_id}")
async def update_category(
    category_id: str,
    data: dict,
    db = Depends(get_database)
):

    service = CategoryService(db)

    return await service.update_category(category_id, data)


@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    db = Depends(get_database)
):

    service = CategoryService(db)

    return await service.delete_category(category_id)