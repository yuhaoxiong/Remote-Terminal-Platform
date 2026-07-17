from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies import bearer_scheme, conflict_error, get_current_user, not_found_error, request_session, require_admin_user
from app.models.user import User
from app.schemas.deployment import (
    DeploymentExecutionItemRead,
    DeploymentExecutionRead,
    DeviceReleaseOverrideRead,
    DeviceReleaseOverrideSet,
    DeploymentPlanCreate,
    DeploymentPlanItemRead,
    DeploymentPlanRead,
)
from app.services.deployment_service import DeploymentConflictError, DeploymentNotFoundError, DeploymentPlanService
from app.services.deployment_execution_service import (
    DeploymentArtifactAuthorizationError,
    DeploymentExecutionConflictError,
    DeploymentExecutionNotFoundError,
    DeploymentExecutionService,
)
from app.services.operation_log import OperationLogService


router = APIRouter(tags=["deployment"])


def _read_plan(plan, items) -> DeploymentPlanRead:
    return DeploymentPlanRead.model_validate(plan).model_copy(
        update={"items": [DeploymentPlanItemRead.model_validate(item) for item in items]}
    )


def _read_execution(execution, items) -> DeploymentExecutionRead:
    return DeploymentExecutionRead.model_validate(execution).model_copy(
        update={"items": [DeploymentExecutionItemRead.model_validate(item) for item in items]}
    )


@router.put(
    "/devices/{device_id}/release-overrides/{function_id}",
    response_model=DeviceReleaseOverrideRead,
)
def set_device_release_override(
    device_id: int,
    function_id: int,
    payload: DeviceReleaseOverrideSet,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> DeviceReleaseOverrideRead:
    with request_session(request) as (settings, session):
        try:
            override = DeploymentPlanService(settings).set_override(
                session,
                device_id=device_id,
                function_id=function_id,
                release_id=payload.release_id,
                reason=payload.reason,
                expires_at=payload.expires_at,
                created_by=current_user.id,
            )
        except DeploymentNotFoundError as exc:
            raise not_found_error(exc) from exc
        except DeploymentConflictError as exc:
            raise conflict_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="deployment.override.set",
            target_type="device_release_override",
            target_id=override.id,
            status="active",
            detail=override.reason,
        )
        return DeviceReleaseOverrideRead.model_validate(override)


@router.post(
    "/projects/{project_id}/deployment-plans",
    response_model=DeploymentPlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_deployment_plan(
    project_id: int,
    payload: DeploymentPlanCreate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> DeploymentPlanRead:
    with request_session(request) as (settings, session):
        try:
            plan, items = DeploymentPlanService(settings).create(
                session,
                project_id=project_id,
                device_ids=payload.device_ids,
                created_by=current_user.id,
            )
        except DeploymentNotFoundError as exc:
            raise not_found_error(exc) from exc
        except DeploymentConflictError as exc:
            raise conflict_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="deployment.plan.create",
            target_type="deployment_plan",
            target_id=plan.id,
            status=plan.status,
            detail=plan.snapshot_hash,
        )
        return _read_plan(plan, items)


@router.get("/deployment-plans/{plan_id}", response_model=DeploymentPlanRead)
def get_deployment_plan(
    plan_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeploymentPlanRead:
    with request_session(request) as (settings, session):
        try:
            plan, items = DeploymentPlanService(settings).get(session, plan_id)
        except DeploymentNotFoundError as exc:
            raise not_found_error(exc) from exc
        return _read_plan(plan, items)


@router.post("/deployment-plans/{plan_id}/confirm", response_model=DeploymentExecutionRead)
def confirm_deployment_plan(
    plan_id: int,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> DeploymentExecutionRead:
    pending_conflict: DeploymentConflictError | None = None
    response: DeploymentExecutionRead | None = None
    with request_session(request) as (settings, session):
        service = DeploymentPlanService(settings)
        try:
            execution, items = service.confirm(
                session,
                plan_id=plan_id,
                confirmed_by=current_user.id,
            )
        except DeploymentNotFoundError as exc:
            raise not_found_error(exc) from exc
        except DeploymentConflictError as exc:
            pending_conflict = exc
            OperationLogService(settings).record(
                session,
                user_id=current_user.id,
                action="deployment.plan.confirm_rejected",
                target_type="deployment_plan",
                target_id=plan_id,
                status="failed",
                detail=str(exc),
            )
        else:
            OperationLogService(settings).record(
                session,
                user_id=current_user.id,
                action="deployment.plan.confirm",
                target_type="deployment_execution",
                target_id=execution.id,
                status=execution.status,
                detail=execution.execution_id,
            )
            response = _read_execution(execution, items)
    if pending_conflict is not None:
        raise conflict_error(pending_conflict)
    assert response is not None
    return response


@router.post("/deployment-executions/{execution_id}/execute", response_model=DeploymentExecutionRead)
def execute_deployment(
    execution_id: str,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> DeploymentExecutionRead:
    with request_session(request) as (settings, session):
        service = DeploymentExecutionService(
            settings,
            ssh_service=getattr(request.app.state, "ssh_service", None),
        )
        try:
            execution, items = service.execute(session, execution_id)
        except DeploymentExecutionNotFoundError as exc:
            raise not_found_error(exc) from exc
        except DeploymentExecutionConflictError as exc:
            raise conflict_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="deployment.execution.execute",
            target_type="deployment_execution",
            target_id=execution.id,
            status=execution.status,
            detail=execution.execution_id,
        )
    return _read_execution(execution, items)


@router.get("/deployment-executions/{execution_id}", response_model=DeploymentExecutionRead)
def get_deployment_execution(
    execution_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeploymentExecutionRead:
    with request_session(request) as (settings, session):
        try:
            execution, items = DeploymentExecutionService(settings).get(session, execution_id)
        except DeploymentExecutionNotFoundError as exc:
            raise not_found_error(exc) from exc
        return _read_execution(execution, items)


@router.get("/deployment-executions/{execution_id}/items/{item_id}/artifact")
def download_deployment_artifact(
    execution_id: str,
    item_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> FileResponse:
    with request_session(request) as (settings, session):
        try:
            path, variant, filename = DeploymentExecutionService(settings).get_artifact(
                session,
                execution_id=execution_id,
                item_id=item_id,
                token=credentials.credentials,
            )
        except DeploymentArtifactAuthorizationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        except DeploymentExecutionNotFoundError as exc:
            raise not_found_error(exc) from exc
        except DeploymentExecutionConflictError as exc:
            raise conflict_error(exc) from exc
        headers = {
            "Accept-Ranges": "bytes",
            "ETag": f'"{variant.artifact_sha256}"',
        }
    return FileResponse(path, media_type="application/gzip", filename=filename, headers=headers)
