from fastapi import APIRouter, Depends
from app.db.mongodb import get_database
from app.services.product_variant_service import ProductVariantService
from app.models.product_variants_model import ProductVariantCreate, ProductVariantUpdate
from app.core.security import get_current_user


router = APIRouter(
    prefix="/product-variants",
    tags=["Product Variants"]
)

@router.post("/")
async def create_variant(
    variant_in: ProductVariantCreate,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ProductVariantService(db)

    data = variant_in.model_dump()

    return await service.create_variant(data)

@router.get("/product/{product_id}")
async def get_product_variants(
    product_id: str,
    db = Depends(get_database)
):

    service = ProductVariantService(db)

    return await service.get_variants_by_product(product_id)

@router.get("/{variant_id}")
async def get_variant(
    variant_id: str,
    db = Depends(get_database)
):

    service = ProductVariantService(db)

    return await service.get_variant(variant_id)

@router.put("/{variant_id}")
async def update_variant(
    variant_id: str,
    variant_update: ProductVariantUpdate,
    db = Depends(get_database)
):

    service = ProductVariantService(db)

    data = variant_update.model_dump(exclude_unset=True)

    return await service.update_variant(variant_id, data)

@router.delete("/{variant_id}")
async def delete_variant(
    variant_id: str,
    db = Depends(get_database)
):

    service = ProductVariantService(db)

    return await service.delete_variant(variant_id)