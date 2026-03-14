from pydantic import BaseModel
from typing import List


class DashboardStats(BaseModel):
    total_users: int
    total_shops: int
    total_posts: int
    total_reports: int


class CategoryStats(BaseModel):
    category: str
    count: int
    percentage: float


class VisitStats(BaseModel):
    day: str
    visits: int