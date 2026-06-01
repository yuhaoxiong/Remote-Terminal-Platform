from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import Settings, get_settings
from app.database import get_engine, init_db
from app.routers.alert_notifications import router as alert_notifications_router
from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router
from app.routers.diagnostics import router as diagnostics_router
from app.routers.devices import router as devices_router
from app.routers.frps import router as frps_router
from app.routers.groups import router as groups_router
from app.routers.logs import router as logs_router
from app.routers.monitoring import router as monitoring_router
from app.routers.scheduler import router as scheduler_router
from app.routers.scheduled_tasks import router as scheduled_tasks_router
from app.routers.update_task_templates import router as update_task_templates_router
from app.routers.update_tasks import router as update_tasks_router
from app.websockets.devices import router as device_ws_router
from app.websockets.update_tasks import router as update_task_ws_router
from app.services.scheduler_service import SchedulerService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_db(settings)
    scheduler_service = SchedulerService(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler_service.start()
        yield
        scheduler_service.shutdown()

    app = FastAPI(title="Edge Platform", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    app.state.scheduler_service = scheduler_service

    @app.get(f"{settings.api_prefix}/health", tags=["system"])
    def health_check() -> dict[str, str]:
        database_status = "ok"
        try:
            with get_engine(settings).connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            database_status = "error"
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.version,
            "database": database_status,
        }

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(alerts_router, prefix=settings.api_prefix)
    app.include_router(alert_notifications_router, prefix=settings.api_prefix)
    app.include_router(diagnostics_router, prefix=settings.api_prefix)
    app.include_router(devices_router, prefix=settings.api_prefix)
    app.include_router(frps_router, prefix=settings.api_prefix)
    app.include_router(groups_router, prefix=settings.api_prefix)
    app.include_router(update_tasks_router, prefix=settings.api_prefix)
    app.include_router(update_task_templates_router, prefix=settings.api_prefix)
    app.include_router(logs_router, prefix=settings.api_prefix)
    app.include_router(monitoring_router, prefix=settings.api_prefix)
    app.include_router(scheduled_tasks_router, prefix=settings.api_prefix)
    app.include_router(scheduler_router, prefix=settings.api_prefix)
    app.include_router(device_ws_router, prefix=settings.api_prefix)
    app.include_router(update_task_ws_router, prefix=settings.api_prefix)
    return app


app = create_app()
