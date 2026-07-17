from fastapi import APIRouter, HTTPException, Request, status

from app.dependencies import conflict_error, not_found_error, request_session
from app.schemas.bootstrap import DeviceRegistrationClaim, DeviceRegistrationResponse
from app.services.bootstrap_service import (
    BootstrapConflictError,
    BootstrapNotFoundError,
    BootstrapPackageService,
    BootstrapTokenError,
)
from app.services.operation_log import OperationLogService

router = APIRouter(prefix="/device-registration", tags=["device-registration"])


@router.post("/claim", response_model=DeviceRegistrationResponse)
def claim_device(payload: DeviceRegistrationClaim, request: Request) -> DeviceRegistrationResponse:
    with request_session(request) as (settings, session):
        try:
            device, package, accepted, hardware_matches = BootstrapPackageService(settings).claim(session, payload)
        except BootstrapTokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
        except BootstrapNotFoundError as exc:
            raise not_found_error(exc) from exc
        except BootstrapConflictError as exc:
            raise conflict_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=None,
            action="device.bootstrap.claim",
            target_type="device_bootstrap_package",
            target_id=package.id,
            status="success" if accepted else device.initialization_status,
            detail=f"device={device.device_sn}, generation={package.generation}",
        )
        return DeviceRegistrationResponse(
            device_id=device.id,
            accepted=accepted,
            status=device.initialization_status,
            vnc_status=device.vnc_status,
            hardware_profile_id=device.actual_profile_id,
            hardware_matches_expected=hardware_matches,
        )
