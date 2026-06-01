from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.enums import AlertNotificationEventType, AlertRuleType, AlertSeverity, AlertSourceType, AlertStatus
from app.models.alert import Alert, AlertRule
from app.models.device import Device
from app.models.metric import DeviceMetric
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
from app.models.update_task import UpdateTask, UpdateTaskDevice
from app.schemas.alert import AlertRuleUpdate


class AlertNotFoundError(RuntimeError):
    pass


class AlertRuleNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class AlertDefaults:
    enabled: bool
    severity: str
    threshold_value: float | None = None
    window_minutes: int | None = None


DEFAULT_RULES: dict[str, AlertDefaults] = {
    AlertRuleType.device_status.value: AlertDefaults(True, AlertSeverity.warning.value),
    AlertRuleType.cpu_high.value: AlertDefaults(True, AlertSeverity.warning.value, threshold_value=85),
    AlertRuleType.memory_high.value: AlertDefaults(True, AlertSeverity.warning.value, threshold_value=85),
    AlertRuleType.disk_high.value: AlertDefaults(True, AlertSeverity.critical.value, threshold_value=90),
    AlertRuleType.metrics_stale.value: AlertDefaults(True, AlertSeverity.warning.value, window_minutes=10),
    AlertRuleType.scheduled_task_failed.value: AlertDefaults(True, AlertSeverity.critical.value),
    AlertRuleType.update_task_failed.value: AlertDefaults(True, AlertSeverity.critical.value),
}


class AlertService:
    detail_limit = 2000
    active_statuses = (AlertStatus.open.value, AlertStatus.acknowledged.value)

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ensure_default_rules(self, session: Session) -> None:
        existing = set(session.scalars(select(AlertRule.rule_type)))
        for rule_type, defaults in DEFAULT_RULES.items():
            if rule_type in existing:
                continue
            session.add(
                AlertRule(
                    rule_type=rule_type,
                    enabled=defaults.enabled,
                    severity=defaults.severity,
                    threshold_value=defaults.threshold_value,
                    window_minutes=defaults.window_minutes,
                )
            )
        session.flush()

    def list_rules(self, session: Session) -> tuple[int, list[AlertRule]]:
        self.ensure_default_rules(session)
        statement = select(AlertRule).order_by(AlertRule.id.asc())
        total = session.scalar(select(func.count(AlertRule.id))) or 0
        return total, list(session.scalars(statement))

    def get_rule(self, session: Session, rule_id: int) -> AlertRule:
        rule = session.get(AlertRule, rule_id)
        if rule is None:
            raise AlertRuleNotFoundError(f"Alert rule not found: {rule_id}")
        return rule

    def update_rule(self, session: Session, rule_id: int, payload: AlertRuleUpdate) -> AlertRule:
        rule = self.get_rule(session, rule_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)
        session.flush()
        session.refresh(rule)
        return rule

    def rule_by_type(self, session: Session, rule_type: str) -> AlertRule:
        self.ensure_default_rules(session)
        rule = session.scalar(select(AlertRule).where(AlertRule.rule_type == rule_type))
        if rule is None:
            raise AlertRuleNotFoundError(f"Alert rule not found: {rule_type}")
        return rule

    def trigger_alert(
        self,
        session: Session,
        *,
        alert_type: str,
        severity: str,
        source_type: str,
        source_id: int | None,
        dedupe_key: str,
        title: str,
        summary: str,
        detail: str | None = None,
        device_id: int | None = None,
    ) -> Alert:
        now = datetime.now(timezone.utc)
        alert = session.scalar(
            select(Alert).where(Alert.dedupe_key == dedupe_key, Alert.status.in_(self.active_statuses))
        )
        detail = self._truncate(detail)
        created = alert is None
        if alert is None:
            alert = Alert(
                dedupe_key=dedupe_key,
                alert_type=alert_type,
                severity=severity,
                status=AlertStatus.open.value,
                source_type=source_type,
                source_id=source_id,
                device_id=device_id,
                title=title,
                summary=self._truncate(summary) or "",
                detail=detail,
                first_triggered_at=now,
                last_triggered_at=now,
                trigger_count=1,
            )
            session.add(alert)
        else:
            alert.severity = severity
            alert.source_type = source_type
            alert.source_id = source_id
            alert.device_id = device_id
            alert.title = title
            alert.summary = self._truncate(summary) or ""
            alert.detail = detail
            alert.last_triggered_at = now
            alert.trigger_count += 1
        session.flush()
        session.refresh(alert)
        if created:
            self._record_notification_event(session, alert, AlertNotificationEventType.triggered.value)
        return alert

    def resolve_by_dedupe_key(self, session: Session, dedupe_key: str, *, resolved_by: str = "system") -> int:
        now = datetime.now(timezone.utc)
        alerts = list(session.scalars(select(Alert).where(Alert.dedupe_key == dedupe_key, Alert.status.in_(self.active_statuses))))
        for alert in alerts:
            alert.status = AlertStatus.resolved.value
            alert.resolved_at = now
            alert.resolved_by = resolved_by
        session.flush()
        for alert in alerts:
            self._record_notification_event(session, alert, AlertNotificationEventType.auto_resolved.value)
        return len(alerts)

    def acknowledge(self, session: Session, alert_id: int, *, note: str | None, user_id: int | None) -> Alert:
        alert = self.get(session, alert_id)
        if alert.status == AlertStatus.resolved.value:
            return alert
        alert.status = AlertStatus.acknowledged.value
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_note = note
        session.flush()
        session.refresh(alert)
        self._record_notification_event(session, alert, AlertNotificationEventType.acknowledged.value)
        return alert

    def resolve(self, session: Session, alert_id: int, *, note: str | None, user_id: int | None) -> Alert:
        alert = self.get(session, alert_id)
        alert.status = AlertStatus.resolved.value
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolved_by = f"user:{user_id}" if user_id is not None else "user"
        if note:
            alert.detail = self._truncate(f"{alert.detail or ''}\n手动恢复说明：{note}".strip())
        session.flush()
        session.refresh(alert)
        self._record_notification_event(session, alert, AlertNotificationEventType.resolved.value)
        return alert

    def get(self, session: Session, alert_id: int) -> Alert:
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise AlertNotFoundError(f"Alert not found: {alert_id}")
        return alert

    def list_alerts(
        self,
        session: Session,
        *,
        offset: int,
        limit: int,
        status: str | None = None,
        severity: str | None = None,
        source_type: str | None = None,
        device_id: int | None = None,
        alert_type: str | None = None,
    ) -> tuple[int, list[Alert]]:
        statement = select(Alert)
        count_statement = select(func.count(Alert.id))
        filters: list[Any] = []
        if status:
            filters.append(Alert.status == status)
        if severity:
            filters.append(Alert.severity == severity)
        if source_type:
            filters.append(Alert.source_type == source_type)
        if device_id is not None:
            filters.append(Alert.device_id == device_id)
        if alert_type:
            filters.append(Alert.alert_type == alert_type)
        for condition in filters:
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        total = session.scalar(count_statement) or 0
        alerts = list(session.scalars(statement.order_by(Alert.last_triggered_at.desc(), Alert.id.desc()).offset(offset).limit(limit)))
        return total, alerts

    def summary(self, session: Session) -> dict[str, Any]:
        active_condition = Alert.status.in_(self.active_statuses)
        active_count = session.scalar(select(func.count(Alert.id)).where(active_condition)) or 0
        critical_count = session.scalar(
            select(func.count(Alert.id)).where(active_condition, Alert.severity == AlertSeverity.critical.value)
        ) or 0
        unacknowledged_count = session.scalar(
            select(func.count(Alert.id)).where(Alert.status == AlertStatus.open.value)
        ) or 0
        latest_alert_at = session.scalar(select(func.max(Alert.last_triggered_at)))
        by_source = {
            source_type: count
            for source_type, count in session.execute(
                select(Alert.source_type, func.count(Alert.id)).where(active_condition).group_by(Alert.source_type)
            )
        }
        by_severity = {
            severity: count
            for severity, count in session.execute(
                select(Alert.severity, func.count(Alert.id)).where(active_condition).group_by(Alert.severity)
            )
        }
        return {
            "active_count": active_count,
            "critical_count": critical_count,
            "unacknowledged_count": unacknowledged_count,
            "latest_alert_at": latest_alert_at,
            "by_source": by_source,
            "by_severity": by_severity,
        }

    def evaluate_device_status(self, session: Session, device: Device) -> None:
        rule = self.rule_by_type(session, AlertRuleType.device_status.value)
        key = f"device_status:{device.id}"
        if not rule.enabled or device.status == "online":
            self.resolve_by_dedupe_key(session, key)
            return
        if device.status == "offline":
            severity = AlertSeverity.critical.value
            title = f"设备离线：{device.name}"
        elif device.status in {"unknown", "degraded"}:
            severity = rule.severity
            title = f"设备状态异常：{device.name}"
        else:
            return
        self.trigger_alert(
            session,
            alert_type=AlertRuleType.device_status.value,
            severity=severity,
            source_type=AlertSourceType.device.value,
            source_id=device.id,
            device_id=device.id,
            dedupe_key=key,
            title=title,
            summary=f"设备 {device.device_sn} 当前状态为 {device.status}",
        )

    def evaluate_device_metrics(self, session: Session, device: Device, metric: DeviceMetric) -> None:
        for rule_type, metric_name, value in (
            (AlertRuleType.cpu_high.value, "CPU", metric.cpu_percent),
            (AlertRuleType.memory_high.value, "内存", metric.memory_percent),
            (AlertRuleType.disk_high.value, "磁盘", metric.disk_percent),
        ):
            rule = self.rule_by_type(session, rule_type)
            key = f"{rule_type}:{device.id}"
            threshold = rule.threshold_value
            if not rule.enabled or value is None or threshold is None or value <= threshold:
                self.resolve_by_dedupe_key(session, key)
                continue
            self.trigger_alert(
                session,
                alert_type=rule_type,
                severity=rule.severity,
                source_type=AlertSourceType.metric.value,
                source_id=metric.id,
                device_id=device.id,
                dedupe_key=key,
                title=f"{metric_name} 过高：{device.name}",
                summary=f"{metric_name} 当前 {value:.1f}%，超过阈值 {threshold:.1f}%",
            )
        self.evaluate_device_status(session, device)
        self._evaluate_metric_freshness_for_device(session, device)

    def evaluate_metrics_staleness(self, session: Session, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        count = 0
        for device in session.scalars(select(Device).order_by(Device.id.asc())):
            count += self._evaluate_metric_freshness_for_device(session, device, now=now)
        return count

    def handle_scheduled_task_run(self, session: Session, task: ScheduledTask, run: ScheduledTaskRun) -> None:
        rule = self.rule_by_type(session, AlertRuleType.scheduled_task_failed.value)
        key = f"scheduled_task_failed:{task.id}"
        if run.status == "success":
            self.resolve_by_dedupe_key(session, key)
            return
        if not rule.enabled or run.status != "failed":
            return
        self.trigger_alert(
            session,
            alert_type=AlertRuleType.scheduled_task_failed.value,
            severity=rule.severity,
            source_type=AlertSourceType.scheduled_task.value,
            source_id=task.id,
            dedupe_key=key,
            title=f"定时任务失败：{task.name}",
            summary=run.error_message or run.output_summary or "定时任务执行失败",
            detail=f"run_id={run.id}; update_task_id={run.created_update_task_id}",
        )

    def handle_update_task_completed(self, session: Session, task: UpdateTask) -> None:
        rule = self.rule_by_type(session, AlertRuleType.update_task_failed.value)
        if not rule.enabled:
            return
        rows = list(session.scalars(select(UpdateTaskDevice).where(UpdateTaskDevice.task_id == task.id)))
        failed_rows = [row for row in rows if row.status == "failed"]
        if task.status != "partial_failed" and not failed_rows:
            return
        summary = f"批量任务 {task.name} 存在 {len(failed_rows)} 台失败设备"
        detail = "; ".join(
            f"device_id={row.device_id}: {row.error_message or row.output_summary or row.status}" for row in failed_rows[:5]
        )
        self.trigger_alert(
            session,
            alert_type=AlertRuleType.update_task_failed.value,
            severity=rule.severity,
            source_type=AlertSourceType.update_task.value,
            source_id=task.id,
            dedupe_key=f"update_task_failed:{task.id}",
            title=f"批量任务失败：{task.name}",
            summary=summary,
            detail=detail or None,
        )

    def _evaluate_metric_freshness_for_device(self, session: Session, device: Device, now: datetime | None = None) -> int:
        rule = self.rule_by_type(session, AlertRuleType.metrics_stale.value)
        key = f"metrics_stale:{device.id}"
        latest = session.scalar(
            select(DeviceMetric).where(DeviceMetric.device_id == device.id).order_by(DeviceMetric.recorded_at.desc(), DeviceMetric.id.desc()).limit(1)
        )
        if latest is None:
            self.resolve_by_dedupe_key(session, key)
            return 0
        if not rule.enabled or rule.window_minutes is None:
            self.resolve_by_dedupe_key(session, key)
            return 0
        now = now or datetime.now(timezone.utc)
        recorded_at = latest.recorded_at
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=timezone.utc)
        if recorded_at >= now - timedelta(minutes=rule.window_minutes):
            self.resolve_by_dedupe_key(session, key)
            return 0
        self.trigger_alert(
            session,
            alert_type=AlertRuleType.metrics_stale.value,
            severity=rule.severity,
            source_type=AlertSourceType.metric.value,
            source_id=latest.id,
            device_id=device.id,
            dedupe_key=key,
            title=f"指标过期：{device.name}",
            summary=f"设备 {device.device_sn} 最近指标超过 {rule.window_minutes} 分钟未更新",
        )
        return 1

    def _truncate(self, value: str | None) -> str | None:
        if value is None:
            return None
        return value if len(value) <= self.detail_limit else value[: self.detail_limit] + "...[已截断]"

    def _record_notification_event(self, session: Session, alert: Alert, event_type: str) -> None:
        try:
            from app.services.alert_notification_service import AlertNotificationService

            AlertNotificationService(self.settings).record_event(session, alert, event_type)
        except Exception:
            # Notification delivery must never break the alert lifecycle.
            return
