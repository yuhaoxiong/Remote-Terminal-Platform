from datetime import datetime, timedelta, timezone

from app.database import session_scope
from app.enums import AlertStatus
from app.models.alert import Alert, AlertRule
from app.models.metric import DeviceMetric
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
from app.models.update_task import UpdateTaskDevice
from app.services.alert_service import AlertService
from app.services.scheduled_task_service import ScheduledTaskService
from app.services.update_task_service import UpdateTaskService


def test_metric_threshold_alert_dedupes_and_auto_resolves(client, auth_headers, create_device, initialized_settings) -> None:
    device = create_device()

    high = client.post(
        f"/api/devices/{device.id}/metrics",
        headers=auth_headers,
        json={"status": "online", "cpu_percent": 91, "memory_percent": 20, "disk_percent": 30},
    )
    assert high.status_code == 201
    high_again = client.post(
        f"/api/devices/{device.id}/metrics",
        headers=auth_headers,
        json={"status": "online", "cpu_percent": 92, "memory_percent": 20, "disk_percent": 30},
    )
    assert high_again.status_code == 201

    with session_scope(initialized_settings) as session:
        alerts = list(session.query(Alert).filter(Alert.alert_type == "cpu_high").all())
        assert len(alerts) == 1
        assert alerts[0].trigger_count == 2
        assert alerts[0].status == "open"

    normal = client.post(
        f"/api/devices/{device.id}/metrics",
        headers=auth_headers,
        json={"status": "online", "cpu_percent": 10, "memory_percent": 20, "disk_percent": 30},
    )
    assert normal.status_code == 201

    with session_scope(initialized_settings) as session:
        alert = session.query(Alert).filter(Alert.alert_type == "cpu_high").one()
        assert alert.status == "resolved"
        assert alert.resolved_by == "system"


def test_device_status_alert_auto_resolves(client, auth_headers, create_device, initialized_settings) -> None:
    device = create_device(status="online")

    response = client.put(f"/api/devices/{device.id}", headers=auth_headers, json={"status": "offline"})
    assert response.status_code == 200
    with session_scope(initialized_settings) as session:
        alert = session.query(Alert).filter(Alert.alert_type == "device_status").one()
        assert alert.severity == "critical"
        assert alert.device_id == device.id

    response = client.put(f"/api/devices/{device.id}", headers=auth_headers, json={"status": "online"})
    assert response.status_code == 200
    with session_scope(initialized_settings) as session:
        alert = session.query(Alert).filter(Alert.alert_type == "device_status").one()
        assert alert.status == AlertStatus.resolved.value


def test_metrics_stale_ignores_never_reported_devices(create_device, initialized_settings) -> None:
    create_device()
    with session_scope(initialized_settings) as session:
        count = AlertService(initialized_settings).evaluate_metrics_staleness(session, datetime.now(timezone.utc))
        assert count == 0
        assert session.query(Alert).count() == 0


def test_metrics_stale_alerts_for_old_metric(create_device, initialized_settings) -> None:
    device = create_device()
    with session_scope(initialized_settings) as session:
        session.add(
            DeviceMetric(
                device_id=device.id,
                cpu_percent=10,
                memory_percent=10,
                disk_percent=10,
                recorded_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            )
        )
        session.flush()
        count = AlertService(initialized_settings).evaluate_metrics_staleness(session, datetime.now(timezone.utc))
        assert count == 1
        alert = session.query(Alert).filter(Alert.alert_type == "metrics_stale").one()
        assert alert.status == "open"


def test_scheduled_task_failure_alert_auto_resolves(create_device, initialized_settings) -> None:
    device = create_device()
    with session_scope(initialized_settings) as session:
        task = ScheduledTask(
            name="巡检",
            task_type="command",
            schedule="interval:60",
            command="hostname",
            target_filter={"device_ids": [device.id]},
            enabled=True,
        )
        session.add(task)
        session.flush()
        failed_run = ScheduledTaskRun(scheduled_task_id=task.id, trigger_type="scheduled", status="failed", error_message="失败")
        session.add(failed_run)
        session.flush()
        AlertService(initialized_settings).handle_scheduled_task_run(session, task, failed_run)
        assert session.query(Alert).filter(Alert.alert_type == "scheduled_task_failed").one().status == "open"
        success_run = ScheduledTaskRun(scheduled_task_id=task.id, trigger_type="scheduled", status="success", output_summary="ok")
        session.add(success_run)
        session.flush()
        AlertService(initialized_settings).handle_scheduled_task_run(session, task, success_run)
        assert session.query(Alert).filter(Alert.alert_type == "scheduled_task_failed").one().status == "resolved"


def test_update_task_failure_alert(create_update_task, initialized_settings) -> None:
    task = create_update_task(execution_mode="ssh_command")
    with session_scope(initialized_settings) as session:
        task = session.get(type(task), task.id)
        task.status = "partial_failed"
        row = session.query(UpdateTaskDevice).filter(UpdateTaskDevice.task_id == task.id).one()
        row.status = "failed"
        row.error_message = "SSH 失败"
        AlertService(initialized_settings).handle_update_task_completed(session, task)
        alert = session.query(Alert).filter(Alert.alert_type == "update_task_failed").one()
        assert alert.source_id == task.id
        assert "1 台失败设备" in alert.summary


def test_alert_rule_update_changes_threshold(client, auth_headers, initialized_settings) -> None:
    response = client.get("/api/alert-rules", headers=auth_headers)
    assert response.status_code == 200
    cpu_rule = next(item for item in response.json()["items"] if item["rule_type"] == "cpu_high")

    update = client.put(
        f"/api/alert-rules/{cpu_rule['id']}",
        headers=auth_headers,
        json={"enabled": False, "threshold_value": 95},
    )
    assert update.status_code == 200
    assert update.json()["enabled"] is False
    assert update.json()["threshold_value"] == 95

    with session_scope(initialized_settings) as session:
        rule = session.get(AlertRule, cpu_rule["id"])
        assert rule.enabled is False
        assert rule.threshold_value == 95
