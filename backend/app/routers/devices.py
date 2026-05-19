from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.dependencies import get_app_settings, get_current_user
from app.database import session_scope
from app.models.user import User
from app.schemas.device import (
    DeviceCreate,
    DeviceListResponse,
    DeviceMetricCreate,
    DeviceMetricListResponse,
    DeviceMetricRead,
    DeviceRead,
    DeviceStatusResponse,
    DeviceUpdate,
    RemoteSessionResponse,
    SyncConfigResponse,
)
from app.schemas.file_transfer import FileDeleteRequest, FileListResponse, FileOperationResponse, FileUploadRequest
from app.services.device_service import DeviceDuplicateError, DeviceNotFoundError, DeviceService
from app.services.file_service import FilePathError, FileService, RemoteFileNotFoundError
from app.services.frpc_config import FrpcConfigService
from app.services.monitoring_service import MonitoringService
from app.services.operation_log import OperationLogService
from app.services.port_pool import PortPoolExhaustedError
from app.services.remote_access import RemoteAccessService

router = APIRouter(prefix="/devices", tags=["devices"])


def _read(device) -> DeviceRead:
    return DeviceRead.model_validate(device)


def _not_found(exc: DeviceNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _file_error(exc: FilePathError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeviceRead:
    settings = get_app_settings(request)
    service = DeviceService(settings)
    with session_scope(settings) as session:
        try:
            device = service.create(session, payload)
        except DeviceDuplicateError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except PortPoolExhaustedError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.create",
            target_type="device",
            target_id=device.id,
            status="success",
            detail=device.device_sn,
        )
        return _read(device)


@router.get("", response_model=DeviceListResponse)
def list_devices(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = None,
    project_id: str | None = None,
    group_id: int | None = None,
    tag: str | None = None,
    status: str | None = None,
) -> DeviceListResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        total, devices = DeviceService(settings).list(
            session,
            offset=offset,
            limit=limit,
            search=search,
            project_id=project_id,
            group_id=group_id,
            tag=tag,
            status=status,
        )
        return DeviceListResponse(total=total, items=[_read(device) for device in devices])


@router.get("/{device_id}", response_model=DeviceRead)
def get_device(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeviceRead:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            return _read(DeviceService(settings).get(session, device_id))
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc


@router.put("/{device_id}", response_model=DeviceRead)
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeviceRead:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).update(session, device_id, payload)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.update",
            target_type="device",
            target_id=device.id,
            status="success",
            detail=device.device_sn,
        )
        return _read(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            device_sn = device.device_sn
            DeviceService(settings).delete(session, device_id)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.delete",
            target_type="device",
            target_id=device_id,
            status="success",
            detail=device_sn,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{device_id}/status", response_model=DeviceStatusResponse)
def get_device_status(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeviceStatusResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        return DeviceStatusResponse(id=device.id, status=device.status, last_seen=device.last_seen)


@router.post("/{device_id}/sync-config", response_model=SyncConfigResponse)
def sync_device_config(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> SyncConfigResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        config = FrpcConfigService().generate(device)
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.sync_config",
            target_type="device",
            target_id=device.id,
            status="generated",
            detail=device.device_sn,
        )
        return SyncConfigResponse(device_id=device.id, status="generated", config=config)


@router.get("/{device_id}/files", response_model=FileListResponse)
def list_device_files(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    path: str = Query(default="/"),
) -> FileListResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            items = FileService(settings).list_files(device, path)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        except FilePathError as exc:
            raise _file_error(exc) from exc
        return FileListResponse(device_id=device.id, path=path, items=items)


@router.post("/{device_id}/files/upload", response_model=FileOperationResponse, status_code=status.HTTP_201_CREATED)
def upload_device_file(
    device_id: int,
    payload: FileUploadRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FileOperationResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            size = FileService(settings).upload_text(device, payload.remote_path, payload.content)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        except FilePathError as exc:
            raise _file_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.file_upload",
            target_type="device",
            target_id=device.id,
            status="success",
            detail=payload.remote_path,
        )
        return FileOperationResponse(device_id=device.id, remote_path=payload.remote_path, status="uploaded", size=size)


@router.get("/{device_id}/files/download")
def download_device_file(
    device_id: int,
    remote_path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> Response:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            content = FileService(settings).download_text(device, remote_path)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        except FilePathError as exc:
            raise _file_error(exc) from exc
        except RemoteFileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.file_download",
            target_type="device",
            target_id=device.id,
            status="success",
            detail=remote_path,
        )
    return Response(content=content, media_type="text/plain")


@router.delete("/{device_id}/files", response_model=FileOperationResponse)
def delete_device_file(
    device_id: int,
    payload: FileDeleteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> FileOperationResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            FileService(settings).delete(device, payload.remote_path)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        except FilePathError as exc:
            raise _file_error(exc) from exc
        except RemoteFileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.file_delete",
            target_type="device",
            target_id=device.id,
            status="success",
            detail=payload.remote_path,
        )
        return FileOperationResponse(device_id=device.id, remote_path=payload.remote_path, status="deleted")


@router.post("/{device_id}/metrics", response_model=DeviceMetricRead, status_code=status.HTTP_201_CREATED)
def record_device_metric(
    device_id: int,
    payload: DeviceMetricCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> DeviceMetricRead:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device, metric = MonitoringService(settings).record_metric(session, device_id, payload)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="device.metric",
            target_type="device",
            target_id=device.id,
            status=payload.status,
            detail=device.device_sn,
        )
        metric_read = DeviceMetricRead.model_validate(metric)
        return metric_read.model_copy(update={"status": device.status})


@router.get("/{device_id}/metrics", response_model=DeviceMetricListResponse)
def list_device_metrics(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
) -> DeviceMetricListResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            total, metrics = MonitoringService(settings).list_metrics(session, device_id, limit=limit)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        device = DeviceService(settings).get(session, device_id)
        return DeviceMetricListResponse(
            total=total,
            items=[DeviceMetricRead.model_validate(metric).model_copy(update={"status": device.status}) for metric in metrics],
        )


@router.post("/{device_id}/remote/ssh", response_model=RemoteSessionResponse)
def create_ssh_session(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> RemoteSessionResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            payload = RemoteAccessService().build_ssh_session(device)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        except ValueError as exc:
            OperationLogService(settings).record(
                session,
                user_id=current_user.id,
                action="remote.ssh",
                target_type="device",
                target_id=device_id,
                status="failed",
                detail=str(exc),
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="remote.ssh",
            target_type="device",
            target_id=device.id,
            status="ready",
            detail=device.device_sn,
        )
        return RemoteSessionResponse(**payload)


@router.post("/{device_id}/remote/vnc", response_model=RemoteSessionResponse)
def create_vnc_session(
    device_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> RemoteSessionResponse:
    settings = get_app_settings(request)
    with session_scope(settings) as session:
        try:
            device = DeviceService(settings).get(session, device_id)
            payload = RemoteAccessService().build_vnc_session(device)
        except DeviceNotFoundError as exc:
            raise _not_found(exc) from exc
        except ValueError as exc:
            OperationLogService(settings).record(
                session,
                user_id=current_user.id,
                action="remote.vnc",
                target_type="device",
                target_id=device_id,
                status="failed",
                detail=str(exc),
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="remote.vnc",
            target_type="device",
            target_id=device.id,
            status="ready",
            detail=device.device_sn,
        )
        return RemoteSessionResponse(**payload)
