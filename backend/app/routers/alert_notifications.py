from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.dependencies import conflict_error, get_current_user, not_found_error, request_session
from app.enums import AlertNotificationDeliveryStatus
from app.models.user import User
from app.schemas.alert_notification import (
    AlertNotificationChannelCreate,
    AlertNotificationChannelListResponse,
    AlertNotificationChannelRead,
    AlertNotificationChannelUpdate,
    AlertNotificationDeliveryListResponse,
    AlertNotificationDeliveryRead,
    AlertNotificationPolicyCreate,
    AlertNotificationPolicyListResponse,
    AlertNotificationPolicyRead,
    AlertNotificationPolicyUpdate,
    AlertNotificationSummaryResponse,
)
from app.services.alert_notification_service import (
    AlertNotificationConflictError,
    AlertNotificationNotFoundError,
    AlertNotificationSecretError,
    AlertNotificationService,
)
from app.services.operation_log import OperationLogService

router = APIRouter(tags=["alert-notifications"])


@router.get("/alert-notification-channels", response_model=AlertNotificationChannelListResponse)
def list_alert_notification_channels(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationChannelListResponse:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        total, channels = service.list_channels(session)
        return AlertNotificationChannelListResponse(total=total, items=[service.channel_read(channel) for channel in channels])


@router.post("/alert-notification-channels", response_model=AlertNotificationChannelRead, status_code=status.HTTP_201_CREATED)
def create_alert_notification_channel(
    payload: AlertNotificationChannelCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationChannelRead:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            channel = service.create_channel(session, payload)
        except AlertNotificationSecretError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_channel.create",
            target_type="alert_notification_channel",
            target_id=channel.id,
            status="success",
            detail=channel.name,
        )
        return service.channel_read(channel)


@router.put("/alert-notification-channels/{channel_id}", response_model=AlertNotificationChannelRead)
def update_alert_notification_channel(
    channel_id: int,
    payload: AlertNotificationChannelUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationChannelRead:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            channel = service.update_channel(session, channel_id, payload)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        except AlertNotificationSecretError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_channel.update",
            target_type="alert_notification_channel",
            target_id=channel.id,
            status="success",
            detail=channel.name,
        )
        return service.channel_read(channel)


@router.delete("/alert-notification-channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert_notification_channel(
    channel_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            channel = service.get_channel(session, channel_id)
            name = channel.name
            service.delete_channel(session, channel_id)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        except AlertNotificationConflictError as exc:
            raise conflict_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_channel.delete",
            target_type="alert_notification_channel",
            target_id=channel_id,
            status="success",
            detail=name,
        )


@router.post("/alert-notification-channels/{channel_id}/test", response_model=AlertNotificationChannelRead)
def test_alert_notification_channel(
    channel_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationChannelRead:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            channel = service.test_channel(session, channel_id)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_channel.test",
            target_type="alert_notification_channel",
            target_id=channel.id,
            status=channel.last_test_status or "unknown",
            detail=channel.last_error or channel.name,
        )
        return service.channel_read(channel)


@router.get("/alert-notification-policies", response_model=AlertNotificationPolicyListResponse)
def list_alert_notification_policies(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationPolicyListResponse:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        total, policies = service.list_policies(session)
        return AlertNotificationPolicyListResponse(
            total=total,
            items=[AlertNotificationPolicyRead.model_validate(policy) for policy in policies],
        )


@router.post("/alert-notification-policies", response_model=AlertNotificationPolicyRead, status_code=status.HTTP_201_CREATED)
def create_alert_notification_policy(
    payload: AlertNotificationPolicyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationPolicyRead:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            policy = service.create_policy(session, payload)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_policy.create",
            target_type="alert_notification_policy",
            target_id=policy.id,
            status="success",
            detail=policy.name,
        )
        return AlertNotificationPolicyRead.model_validate(policy)


@router.put("/alert-notification-policies/{policy_id}", response_model=AlertNotificationPolicyRead)
def update_alert_notification_policy(
    policy_id: int,
    payload: AlertNotificationPolicyUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationPolicyRead:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            policy = service.update_policy(session, policy_id, payload)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_policy.update",
            target_type="alert_notification_policy",
            target_id=policy.id,
            status="success",
            detail=policy.name,
        )
        return AlertNotificationPolicyRead.model_validate(policy)


@router.delete("/alert-notification-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert_notification_policy(
    policy_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            policy = service.get_policy(session, policy_id)
            name = policy.name
            service.delete_policy(session, policy_id)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_policy.delete",
            target_type="alert_notification_policy",
            target_id=policy_id,
            status="success",
            detail=name,
        )


@router.get("/alert-notification-deliveries", response_model=AlertNotificationDeliveryListResponse)
def list_alert_notification_deliveries(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: AlertNotificationDeliveryStatus | None = Query(default=None, alias="status"),
    alert_id: int | None = Query(default=None, ge=1),
    channel_id: int | None = Query(default=None, ge=1),
) -> AlertNotificationDeliveryListResponse:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        total, deliveries = service.list_deliveries(
            session,
            offset=offset,
            limit=limit,
            status=status_filter.value if status_filter else None,
            alert_id=alert_id,
            channel_id=channel_id,
        )
        return AlertNotificationDeliveryListResponse(total=total, items=deliveries)


@router.post("/alert-notification-deliveries/{delivery_id}/retry", response_model=AlertNotificationDeliveryRead)
def retry_alert_notification_delivery(
    delivery_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationDeliveryRead:
    with request_session(request) as (settings, session):
        service = AlertNotificationService(settings)
        try:
            delivery = service.retry_delivery(session, delivery_id)
        except AlertNotificationNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_notification_delivery.retry",
            target_type="alert_notification_delivery",
            target_id=delivery.id,
            status=delivery.status,
            detail=delivery.error_message or delivery.response_summary,
        )
        return service.delivery_read(session, delivery)


@router.get("/alert-notification-summary", response_model=AlertNotificationSummaryResponse)
def alert_notification_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertNotificationSummaryResponse:
    with request_session(request) as (settings, session):
        return AlertNotificationSummaryResponse(**AlertNotificationService(settings).summary(session))
