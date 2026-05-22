from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.scheduled_task import SchedulerStatusResponse
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatusResponse)
def scheduler_status(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> SchedulerStatusResponse:
    service = getattr(request.app.state, "scheduler_service", None)
    if not isinstance(service, SchedulerService):
        settings = request.app.state.settings
        service = SchedulerService(settings)
    status = service.status()
    return SchedulerStatusResponse(**status.__dict__)
