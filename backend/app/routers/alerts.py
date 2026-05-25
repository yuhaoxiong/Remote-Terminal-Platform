from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_current_user, not_found_error, request_session
from app.enums import AlertSeverity, AlertSourceType, AlertStatus
from app.models.user import User
from app.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertListResponse,
    AlertRead,
    AlertResolveRequest,
    AlertRuleListResponse,
    AlertRuleRead,
    AlertRuleUpdate,
    AlertSummaryResponse,
)
from app.services.alert_service import AlertNotFoundError, AlertRuleNotFoundError, AlertService
from app.services.operation_log import OperationLogService

router = APIRouter(tags=["alerts"])


@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    request: Request,
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    source_type: AlertSourceType | None = None,
    device_id: int | None = Query(default=None, ge=1),
    alert_type: str | None = None,
) -> AlertListResponse:
    with request_session(request) as (settings, session):
        total, alerts = AlertService(settings).list_alerts(
            session,
            offset=offset,
            limit=limit,
            status=status.value if status else None,
            severity=severity.value if severity else None,
            source_type=source_type.value if source_type else None,
            device_id=device_id,
            alert_type=alert_type,
        )
        return AlertListResponse(total=total, items=[AlertRead.model_validate(alert) for alert in alerts])


@router.get("/alerts/summary", response_model=AlertSummaryResponse)
def alert_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertSummaryResponse:
    with request_session(request) as (settings, session):
        return AlertSummaryResponse(**AlertService(settings).summary(session))


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledgeRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertRead:
    with request_session(request) as (settings, session):
        try:
            alert = AlertService(settings).acknowledge(session, alert_id, note=payload.note, user_id=current_user.id)
        except AlertNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert.acknowledge",
            target_type="alert",
            target_id=alert.id,
            status="success",
            detail=payload.note or alert.title,
        )
        return AlertRead.model_validate(alert)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertRead)
def resolve_alert(
    alert_id: int,
    payload: AlertResolveRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertRead:
    with request_session(request) as (settings, session):
        try:
            alert = AlertService(settings).resolve(session, alert_id, note=payload.note, user_id=current_user.id)
        except AlertNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert.resolve",
            target_type="alert",
            target_id=alert.id,
            status="success",
            detail=payload.note or alert.title,
        )
        return AlertRead.model_validate(alert)


@router.get("/alert-rules", response_model=AlertRuleListResponse)
def list_alert_rules(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertRuleListResponse:
    with request_session(request) as (settings, session):
        total, rules = AlertService(settings).list_rules(session)
        return AlertRuleListResponse(total=total, items=[AlertRuleRead.model_validate(rule) for rule in rules])


@router.put("/alert-rules/{rule_id}", response_model=AlertRuleRead)
def update_alert_rule(
    rule_id: int,
    payload: AlertRuleUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> AlertRuleRead:
    with request_session(request) as (settings, session):
        try:
            rule = AlertService(settings).update_rule(session, rule_id, payload)
        except AlertRuleNotFoundError as exc:
            raise not_found_error(exc) from exc
        OperationLogService(settings).record(
            session,
            user_id=current_user.id,
            action="alert_rule.update",
            target_type="alert_rule",
            target_id=rule.id,
            status="success",
            detail=rule.rule_type,
        )
        return AlertRuleRead.model_validate(rule)
