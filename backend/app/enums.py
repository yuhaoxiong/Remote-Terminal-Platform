from enum import Enum


class StrEnum(str, Enum):
    pass


class DeviceStatus(StrEnum):
    online = "online"
    offline = "offline"
    degraded = "degraded"
    unknown = "unknown"


class SshAuthType(StrEnum):
    password = "password"
    key = "key"


class ExecutionMode(StrEnum):
    dry_run = "dry_run"
    ssh_command = "ssh_command"


class FailureStrategy(StrEnum):
    continue_ = "continue"
    pause = "pause"
    rollback = "rollback"


class UpdateTaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    canceled = "canceled"
    partial_failed = "partial_failed"


class UpdateTaskDeviceStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"
    canceled = "canceled"
    completed = "completed"


class FileBackend(StrEnum):
    local = "local"
    sftp = "sftp"


class ScheduledTaskType(StrEnum):
    command = "command"
    script = "script"
    config = "config"
    health_check = "health_check"


class ScheduledTaskRunTriggerType(StrEnum):
    manual = "manual"
    scheduled = "scheduled"


class ScheduledTaskRunStatus(StrEnum):
    running = "running"
    success = "success"
    failed = "failed"
    skipped = "skipped"


class AlertSeverity(StrEnum):
    warning = "warning"
    critical = "critical"


class AlertStatus(StrEnum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class AlertSourceType(StrEnum):
    device = "device"
    metric = "metric"
    scheduled_task = "scheduled_task"
    update_task = "update_task"


class AlertRuleType(StrEnum):
    device_status = "device_status"
    cpu_high = "cpu_high"
    memory_high = "memory_high"
    disk_high = "disk_high"
    metrics_stale = "metrics_stale"
    scheduled_task_failed = "scheduled_task_failed"
    update_task_failed = "update_task_failed"
