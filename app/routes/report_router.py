from fastapi import APIRouter, Depends
from app.services.report_service import ReportService
from app.core.security import get_current_user
from app.db.mongodb import get_database

router = APIRouter(prefix="/reports", tags=["Reports"])
@router.post("/")
async def create_report(
    data: dict,
    db = Depends(get_database),
    current_user = Depends(get_current_user)
):

    service = ReportService(db)

    data["reporter_id"] = str(current_user.id)

    return await service.create_report(data)

@router.get("/type/{target_type}")
async def get_reports_by_type(
    target_type: str,
    db = Depends(get_database)
):

    service = ReportService(db)

    return await service.get_reports_by_type(target_type)

@router.get("/target/{target_id}")
async def get_reports_of_target(
    target_id: str,
    db = Depends(get_database)
):

    service = ReportService(db)

    return await service.get_reports_of_target(target_id)

# Admin update report status
@router.put("/{report_id}/status")
async def update_report_status(
    report_id: str,
    status: str,
    db = Depends(get_database)
):

    service = ReportService(db)

    return await service.update_report_status(report_id, status)

@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    db = Depends(get_database)
):

    service = ReportService(db)

    return await service.delete_report(report_id)