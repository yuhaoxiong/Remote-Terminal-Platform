from fastapi import APIRouter, Depends, Request

from app.database import session_scope
from app.dependencies import get_app_settings, get_current_user
from app.models.user import User
from app.schemas.monitoring import MonitoringOverviewResponse
from app.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/overview", response_model=MonitoringOverviewResponse)
def monitoring_overview(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> MonitoringOverviewResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        return MonitoringOverviewResponse(**MonitoringService(settings).overview(session))
