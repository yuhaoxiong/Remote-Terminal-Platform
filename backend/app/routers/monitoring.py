from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user, request_session
from app.models.user import User
from app.schemas.monitoring import MonitoringOverviewResponse
from app.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/overview", response_model=MonitoringOverviewResponse)
def monitoring_overview(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> MonitoringOverviewResponse:
    with request_session(request) as (settings, session):
        return MonitoringOverviewResponse(**MonitoringService(settings).overview(session))
