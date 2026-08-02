from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.admin import require_active_admin
from app.dependencies.database import get_db
from app.models.admin_user import AdminUser
from app.schemas.admin_dashboard import AdminDashboardSummaryResponse
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


def get_admin_dashboard_service(db: Session = Depends(get_db)) -> AdminDashboardService:
    return AdminDashboardService(db)


@router.get("/summary", response_model=AdminDashboardSummaryResponse)
def dashboard_summary(
    _admin: AdminUser = Depends(require_active_admin),
    service: AdminDashboardService = Depends(get_admin_dashboard_service),
) -> AdminDashboardSummaryResponse:
    return service.get_summary()