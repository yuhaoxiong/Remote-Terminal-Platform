from fastapi import FastAPI

from app.config import Settings, get_settings
from app.database import init_db
from app.routers.auth import router as auth_router
from app.routers.devices import router as devices_router
from app.routers.frps import router as frps_router
from app.routers.groups import router as groups_router
from app.routers.logs import router as logs_router
from app.routers.monitoring import router as monitoring_router
from app.routers.scheduled_tasks import router as scheduled_tasks_router
from app.routers.update_tasks import router as update_tasks_router
from app.websockets.devices import router as device_ws_router
from app.websockets.update_tasks import router as update_task_ws_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    init_db(settings)
    app = FastAPI(title="Edge Platform", version=settings.version)
    app.state.settings = settings

    @app.get(f"{settings.api_prefix}/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
            "version": settings.version,
        }

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(devices_router, prefix=settings.api_prefix)
    app.include_router(frps_router, prefix=settings.api_prefix)
    app.include_router(groups_router, prefix=settings.api_prefix)
    app.include_router(update_tasks_router, prefix=settings.api_prefix)
    app.include_router(logs_router, prefix=settings.api_prefix)
    app.include_router(monitoring_router, prefix=settings.api_prefix)
    app.include_router(scheduled_tasks_router, prefix=settings.api_prefix)
    app.include_router(device_ws_router, prefix=settings.api_prefix)
    app.include_router(update_task_ws_router, prefix=settings.api_prefix)
    return app


app = create_app()
