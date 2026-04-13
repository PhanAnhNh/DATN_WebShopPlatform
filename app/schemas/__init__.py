# app/schemas/__init__.py
from .base import PyObjectId, BaseSchema, ResponseSchema, PaginatedResponse
from .locations import (
    LocationBase, 
    LocationCreate, 
    LocationUpdate,
    ProvinceBase, 
    ProvinceCreate, 
    ProvinceUpdate,
    LocationFilter
)

# Chỉ export những class đã định nghĩa
__all__ = [
    'PyObjectId',
    'BaseSchema', 
    'ResponseSchema',
    'PaginatedResponse',
    'LocationBase',
    'LocationCreate',
    'LocationUpdate',
    'ProvinceBase',
    'ProvinceCreate',
    'ProvinceUpdate',
    'LocationFilter'
]