from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.dependencies import get_app_settings, request_session, require_admin_user
from app.models.user import User
from app.schemas.system_setting import (
    SystemSettingChangeListResponse,
    SystemSettingChangeRead,
    SystemSettingEffectiveResponse,
    SystemSettingGroupUpdate,
    SystemSettingGroupUpdateResponse,
    SystemSettingResetResponse,
    SystemSettingRestartRequest,
    SystemSettingRestartResponse,
    SystemSettingSchemaItem,
    SystemSettingSchemaResponse,
)
from app.services.system_settings import (
    GROUPS,
    SystemSettingError,
    SystemSettingService,
    is_systemd_managed,
    schedule_process_exit,
)

router = APIRouter(prefix="/system-settings", tags=["system-settings"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _service(request: Request) -> SystemSettingService:
    return SystemSettingService(getattr(request.app.state, "base_settings", get_app_settings(request)))


def _refresh_runtime_settings(request: Request) -> None:
    service = _service(request)
    request.app.state.settings = service.load_effective_settings(include_pending=False)


def _effective_response(request: Request) -> SystemSettingEffectiveResponse:
    service = _service(request)
    with request_session(request) as (_settings, session):
        items = service.effective_items(session)
        return SystemSettingEffectiveResponse(
            items=items,
            pending_restart_count=service.pending_restart_count(session),
            database_override_count=service.database_override_count(session),
            credential_encryption_configured=bool(service.base_settings.credential_encryption_key),
            systemd_managed=is_systemd_managed(),
        )


@router.get("/schema", response_model=SystemSettingSchemaResponse)
def get_system_setting_schema(
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> SystemSettingSchemaResponse:
    service = _service(request)
    return SystemSettingSchemaResponse(
        groups=GROUPS,
        items=[
            SystemSettingSchemaItem(
                key=item.key,
                name=item.name,
                description=item.description,
                category=item.category,
                value_type=item.value_type,
                editable=item.editable,
                secret=item.secret,
                requires_restart=item.requires_restart,
                runtime_effective=item.runtime_effective,
                options=list(item.options) if item.options else None,
                min_value=item.min_value,
                max_value=item.max_value,
            )
            for item in service.schema_items()
        ],
    )


@router.get("/effective", response_model=SystemSettingEffectiveResponse)
def get_effective_system_settings(
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> SystemSettingEffectiveResponse:
    return _effective_response(request)


@router.put("/groups/{group_key}", response_model=SystemSettingGroupUpdateResponse)
def update_system_setting_group(
    group_key: str,
    payload: SystemSettingGroupUpdate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> SystemSettingGroupUpdateResponse:
    service = _service(request)
    with request_session(request) as (_settings, session):
        try:
            updated_keys, requires_restart = service.save_group(
                session,
                group_key=group_key,
                values=payload.values,
                actor=current_user,
                client_ip=_client_ip(request),
            )
        except SystemSettingError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        pending_count = service.pending_restart_count(session)
        items = service.effective_items(session)
    _refresh_runtime_settings(request)
    return SystemSettingGroupUpdateResponse(
        group=group_key,
        updated_keys=updated_keys,
        requires_restart=requires_restart,
        pending_restart_count=pending_count,
        items=items,
    )


@router.post("/{key}/reset", response_model=SystemSettingResetResponse)
def reset_system_setting(
    key: str,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> SystemSettingResetResponse:
    service = _service(request)
    with request_session(request) as (_settings, session):
        try:
            spec = service.reset(session, key=key, actor=current_user, client_ip=_client_ip(request))
        except SystemSettingError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        pending_count = service.pending_restart_count(session)
    _refresh_runtime_settings(request)
    return SystemSettingResetResponse(
        key=key,
        source="system",
        requires_restart=spec.requires_restart,
        pending_restart_count=pending_count,
    )


@router.get("/changes", response_model=SystemSettingChangeListResponse)
def list_system_setting_changes(
    request: Request,
    current_user: User = Depends(require_admin_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    setting_key: str | None = None,
    category: str | None = None,
) -> SystemSettingChangeListResponse:
    service = _service(request)
    with request_session(request) as (_settings, session):
        total, items = service.list_changes(
            session,
            offset=offset,
            limit=limit,
            setting_key=setting_key,
            category=category,
        )
        return SystemSettingChangeListResponse(
            total=total,
            items=[SystemSettingChangeRead.model_validate(item) for item in items],
        )


@router.post("/restart", response_model=SystemSettingRestartResponse, status_code=status.HTTP_202_ACCEPTED)
def restart_service(
    payload: SystemSettingRestartRequest,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> SystemSettingRestartResponse:
    if payload.confirm_text != "确认重启":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请输入“确认重启”后再执行")
    if not is_systemd_managed():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前运行环境未检测到 systemd 托管，已拒绝重启")
    service = _service(request)
    with request_session(request) as (settings, session):
        from app.services.operation_log import OperationLogService

        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="system_settings.restart",
            target_type="system_settings",
            target_id=None,
            status="success",
            detail="admin requested service restart",
        )
    schedule_process_exit()
    return SystemSettingRestartResponse(status="restarting", message="服务正在重启")
