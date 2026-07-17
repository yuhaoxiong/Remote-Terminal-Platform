from fastapi import APIRouter, Depends, Query, Request, status

from app.dependencies import conflict_error, get_current_user, not_found_error, request_session, require_admin_user
from app.models.user import User
from app.schemas.lifecycle import (
    FunctionCreate,
    FunctionListResponse,
    FunctionRead,
    FunctionReleaseCreate,
    FunctionReleaseListResponse,
    FunctionReleaseRead,
    FunctionReleaseUpdate,
    FunctionUpdate,
    FunctionVariantCreate,
    FunctionVariantListResponse,
    FunctionVariantRead,
    FunctionVariantUpdate,
    HardwareProfileListResponse,
    HardwareProfileRead,
    ProjectCreate,
    ProjectFunctionListResponse,
    ProjectFunctionRead,
    ProjectFunctionSet,
    ProjectListResponse,
    ProjectRead,
    ProjectUpdate,
)
from app.services.lifecycle_service import (
    FunctionService,
    HardwareProfileService,
    LifecycleConflictError,
    LifecycleImmutableError,
    LifecycleNotFoundError,
    ProjectService,
)
from app.services.operation_log import OperationLogService

router = APIRouter(tags=["lifecycle"])


def _not_found(exc: LifecycleNotFoundError):
    return not_found_error(exc)


def _conflict(exc: Exception):
    return conflict_error(exc)


def _record(request: Request, session, user: User, action: str, target_type: str, target_id: int, detail: str) -> None:
    OperationLogService(request.app.state.settings).record(
        session,
        user_id=user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        status="success",
        detail=detail,
    )


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ProjectListResponse:
    with request_session(request) as (_settings, session):
        total, items = ProjectService().list(session, offset=offset, limit=limit)
        return ProjectListResponse(total=total, items=[ProjectRead.model_validate(item) for item in items])


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> ProjectRead:
    with request_session(request) as (_settings, session):
        try:
            project = ProjectService().create(session, payload)
        except LifecycleConflictError as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "project.create", "project", project.id, project.code)
        return ProjectRead.model_validate(project)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    with request_session(request) as (_settings, session):
        try:
            return ProjectRead.model_validate(ProjectService().get(session, project_id))
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc


@router.put("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> ProjectRead:
    with request_session(request) as (_settings, session):
        try:
            project = ProjectService().update(session, project_id, payload)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        _record(request, session, current_user, "project.update", "project", project.id, project.code)
        return ProjectRead.model_validate(project)


@router.get("/projects/{project_id}/functions", response_model=ProjectFunctionListResponse)
def list_project_functions(
    project_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ProjectFunctionListResponse:
    with request_session(request) as (_settings, session):
        try:
            total, items = ProjectService().list_functions(session, project_id)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        return ProjectFunctionListResponse(
            total=total,
            items=[ProjectFunctionRead.model_validate(item) for item in items],
        )


@router.put("/projects/{project_id}/functions/{function_id}", response_model=ProjectFunctionRead)
def set_project_function(
    project_id: int,
    function_id: int,
    payload: ProjectFunctionSet,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> ProjectFunctionRead:
    with request_session(request) as (_settings, session):
        try:
            item = ProjectService().set_function(session, project_id, function_id, payload)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        except LifecycleConflictError as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "project.function.set", "project_function", item.id, str(item.desired_release_id))
        return ProjectFunctionRead.model_validate(item)


@router.post(
    "/projects/{project_id}/functions/{function_id}/pending-uninstall",
    response_model=ProjectFunctionRead,
)
def mark_project_function_pending_uninstall(
    project_id: int,
    function_id: int,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> ProjectFunctionRead:
    with request_session(request) as (_settings, session):
        try:
            item = ProjectService().mark_pending_uninstall(session, project_id, function_id)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        _record(request, session, current_user, "project.function.pending_uninstall", "project_function", item.id, "confirmed")
        return ProjectFunctionRead.model_validate(item)


@router.get("/hardware-profiles", response_model=HardwareProfileListResponse)
def list_hardware_profiles(
    request: Request,
    current_user: User = Depends(get_current_user),
    active_only: bool = True,
) -> HardwareProfileListResponse:
    with request_session(request) as (_settings, session):
        total, items = HardwareProfileService().list(session, active_only=active_only)
        return HardwareProfileListResponse(
            total=total,
            items=[HardwareProfileRead.model_validate(item) for item in items],
        )


@router.get("/functions", response_model=FunctionListResponse)
def list_functions(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> FunctionListResponse:
    with request_session(request) as (_settings, session):
        total, items = FunctionService().list(session, offset=offset, limit=limit)
        return FunctionListResponse(total=total, items=[FunctionRead.model_validate(item) for item in items])


@router.post("/functions", response_model=FunctionRead, status_code=status.HTTP_201_CREATED)
def create_function(
    payload: FunctionCreate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionRead:
    with request_session(request) as (_settings, session):
        try:
            item = FunctionService().create(session, payload)
        except LifecycleConflictError as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "function.create", "function", item.id, item.code)
        return FunctionRead.model_validate(item)


@router.put("/functions/{function_id}", response_model=FunctionRead)
def update_function(
    function_id: int,
    payload: FunctionUpdate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionRead:
    with request_session(request) as (_settings, session):
        try:
            item = FunctionService().update(session, function_id, payload)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        _record(request, session, current_user, "function.update", "function", item.id, item.code)
        return FunctionRead.model_validate(item)


@router.get("/functions/{function_id}/releases", response_model=FunctionReleaseListResponse)
def list_function_releases(
    function_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FunctionReleaseListResponse:
    with request_session(request) as (_settings, session):
        try:
            total, items = FunctionService().list_releases(session, function_id)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        return FunctionReleaseListResponse(
            total=total,
            items=[FunctionReleaseRead.model_validate(item) for item in items],
        )


@router.post(
    "/functions/{function_id}/releases",
    response_model=FunctionReleaseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_function_release(
    function_id: int,
    payload: FunctionReleaseCreate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionReleaseRead:
    with request_session(request) as (_settings, session):
        try:
            release = FunctionService().create_release(session, function_id, payload, created_by=current_user.id)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        except LifecycleConflictError as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "function.release.create", "function_release", release.id, release.version)
        return FunctionReleaseRead.model_validate(release)


@router.put("/functions/{function_id}/releases/{release_id}", response_model=FunctionReleaseRead)
def update_function_release(
    function_id: int,
    release_id: int,
    payload: FunctionReleaseUpdate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionReleaseRead:
    with request_session(request) as (_settings, session):
        try:
            release = FunctionService().update_release(session, function_id, release_id, payload)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        except LifecycleImmutableError as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "function.release.update", "function_release", release.id, release.version)
        return FunctionReleaseRead.model_validate(release)


@router.get(
    "/functions/{function_id}/releases/{release_id}/variants",
    response_model=FunctionVariantListResponse,
)
def list_function_variants(
    function_id: int,
    release_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FunctionVariantListResponse:
    with request_session(request) as (_settings, session):
        try:
            total, items = FunctionService().list_variants(session, function_id, release_id)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        return FunctionVariantListResponse(
            total=total,
            items=[FunctionVariantRead.model_validate(item) for item in items],
        )


@router.post(
    "/functions/{function_id}/releases/{release_id}/variants",
    response_model=FunctionVariantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_function_variant(
    function_id: int,
    release_id: int,
    payload: FunctionVariantCreate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionVariantRead:
    with request_session(request) as (_settings, session):
        try:
            variant = FunctionService().add_variant(session, function_id, release_id, payload)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        except (LifecycleConflictError, LifecycleImmutableError) as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "function.variant.create", "function_variant", variant.id, variant.artifact_sha256)
        return FunctionVariantRead.model_validate(variant)


@router.put(
    "/functions/{function_id}/releases/{release_id}/variants/{variant_id}",
    response_model=FunctionVariantRead,
)
def update_function_variant(
    function_id: int,
    release_id: int,
    variant_id: int,
    payload: FunctionVariantUpdate,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionVariantRead:
    with request_session(request) as (_settings, session):
        try:
            variant = FunctionService().update_variant(session, function_id, release_id, variant_id, payload)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        except LifecycleImmutableError as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "function.variant.update", "function_variant", variant.id, variant.artifact_sha256)
        return FunctionVariantRead.model_validate(variant)


@router.post(
    "/functions/{function_id}/releases/{release_id}/publish",
    response_model=FunctionReleaseRead,
)
def publish_function_release(
    function_id: int,
    release_id: int,
    request: Request,
    current_user: User = Depends(require_admin_user),
) -> FunctionReleaseRead:
    with request_session(request) as (_settings, session):
        try:
            release = FunctionService().publish_release(session, function_id, release_id)
        except LifecycleNotFoundError as exc:
            raise _not_found(exc) from exc
        except (LifecycleConflictError, LifecycleImmutableError) as exc:
            raise _conflict(exc) from exc
        _record(request, session, current_user, "function.release.publish", "function_release", release.id, release.version)
        return FunctionReleaseRead.model_validate(release)
