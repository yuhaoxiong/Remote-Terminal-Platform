from datetime import datetime, timedelta, timezone

from app.database import session_scope
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun
from app.services.scheduler_service import SchedulerService


def test_wave18_scheduled_task_run_now_and_runs_api(client, auth_headers) -> None:
    created = client.post(
        "/api/scheduled-tasks",
        headers=auth_headers,
        json={
            "name": "Wave 18 manual check",
            "task_type": "health_check",
            "schedule": "interval:60",
            "command": "hostname",
        },
    )
    assert created.status_code == 201
    assert created.json()["next_run_at"] is not None

    executed = client.post(f"/api/scheduled-tasks/{created.json()['id']}/run-now", headers=auth_headers)
    assert executed.status_code == 200
    assert executed.json()["status"] == "success"
    assert executed.json()["run_id"] is not None

    runs = client.get(f"/api/scheduled-tasks/{created.json()['id']}/runs", headers=auth_headers)
    assert runs.status_code == 200
    assert runs.json()["total"] == 1
    assert runs.json()["items"][0]["trigger_type"] == "manual"
    assert runs.json()["items"][0]["status"] == "success"


def test_wave18_invalid_cron_expression_returns_422(client, auth_headers) -> None:
    response = client.post(
        "/api/scheduled-tasks",
        headers=auth_headers,
        json={
            "name": "Invalid cron",
            "task_type": "command",
            "schedule": "cron:* * *",
            "command": "hostname",
        },
    )

    assert response.status_code == 422
    assert "5 位" in str(response.json())


def test_wave18_scheduler_status_endpoint(client, auth_headers) -> None:
    response = client.get("/api/scheduler/status", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["running"] is False
    assert response.json()["poll_interval_seconds"] == 30


def test_wave18_scheduler_scan_executes_due_ssh_task(initialized_settings, create_device, fake_ssh_service) -> None:
    device = create_device(device_sn="wave18-scheduler-device")
    with session_scope(initialized_settings) as session:
        task = ScheduledTask(
            name="Wave 18 scheduled SSH",
            task_type="command",
            schedule="interval:60",
            command="hostname",
            target_filter={"device_ids": [device.id]},
            execution_mode="ssh_command",
            failure_strategy="continue",
            concurrency_limit=1,
            enabled=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(task)
        session.flush()
        task_id = task.id

    fake_ssh = fake_ssh_service()
    scheduler = SchedulerService(initialized_settings.model_copy(update={"scheduler_enabled": True}), ssh_service=fake_ssh)
    assert scheduler.scan_due_tasks() == 1

    with session_scope(initialized_settings) as session:
        task = session.get(ScheduledTask, task_id)
        runs = list(session.query(ScheduledTaskRun).filter_by(scheduled_task_id=task_id).all())

    assert task is not None
    assert task.running is False
    assert task.last_status == "success"
    assert task.next_run_at is not None
    assert len(runs) == 1
    assert runs[0].trigger_type == "scheduled"
    assert runs[0].status == "success"
    assert runs[0].created_update_task_id is not None
    assert len(fake_ssh.calls) == 1


def test_wave18_scheduler_scan_skips_running_tasks(initialized_settings) -> None:
    with session_scope(initialized_settings) as session:
        task = ScheduledTask(
            name="Wave 18 running task",
            task_type="command",
            schedule="interval:60",
            command="hostname",
            execution_mode="dry_run",
            failure_strategy="continue",
            concurrency_limit=1,
            enabled=True,
            running=True,
            next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(task)
        session.flush()
        task_id = task.id

    scheduler = SchedulerService(initialized_settings)
    assert scheduler.scan_due_tasks() == 0

    with session_scope(initialized_settings) as session:
        runs = list(session.query(ScheduledTaskRun).filter_by(scheduled_task_id=task_id).all())

    assert runs == []
