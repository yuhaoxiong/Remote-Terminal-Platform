import type { Mocked } from "vitest";
import type * as healthApi from "../../api/health";
import type * as platformApi from "../../api/platform";

type PlatformApiMock = Mocked<typeof platformApi>;
type HealthApiMock = Mocked<typeof healthApi>;

function setupHealthAndAuthMocks(api: PlatformApiMock, health: HealthApiMock) {
  health.fetchHealth.mockResolvedValue({
    status: "ok",
    service: "edge-platform",
    version: "0.1.0",
  });

  api.loginAdmin.mockResolvedValue({
    access_token: "access-token",
    refresh_token: "refresh-token",
    token_type: "bearer",
  });

  api.getCurrentUser.mockResolvedValue({
    id: 1,
    username: "admin",
    role: "admin",
    is_active: true,
  });
}

function setupUserMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listUsers.mockResolvedValue({
    total: 2,
    items: [
      {
        id: 1,
        username: "admin",
        role: "admin",
        is_active: true,
        last_login_at: "2026-06-04T10:00:00",
        last_login_ip: "127.0.0.1",
        password_changed_at: "2026-06-04T09:00:00",
        created_at: "2026-05-11T00:00:00",
        updated_at: "2026-06-04T10:00:00",
      },
      {
        id: 2,
        username: "operator",
        role: "operator",
        is_active: true,
        last_login_at: null,
        last_login_ip: null,
        password_changed_at: null,
        created_at: "2026-06-04T00:00:00",
        updated_at: "2026-06-04T00:00:00",
      },
    ],
  });

  api.createUser.mockResolvedValue({
    id: 3,
    username: "ops2",
    role: "operator",
    is_active: true,
    last_login_at: null,
    last_login_ip: null,
    password_changed_at: null,
    created_at: "2026-06-04T11:00:00",
    updated_at: "2026-06-04T11:00:00",
  });

  api.updateUser.mockImplementation(async (userId, payload) => ({
    id: userId,
    username: userId === 1 ? "admin" : "operator",
    role: payload.role ?? "operator",
    is_active: payload.is_active ?? true,
    last_login_at: null,
    last_login_ip: null,
    password_changed_at: null,
    created_at: "2026-06-04T00:00:00",
    updated_at: "2026-06-04T11:00:00",
  }));

  api.resetUserPassword.mockImplementation(async (userId) => ({
    id: userId,
    username: userId === 1 ? "admin" : "operator",
    role: userId === 1 ? "admin" : "operator",
    is_active: true,
    last_login_at: null,
    last_login_ip: null,
    password_changed_at: "2026-06-04T11:00:00",
    created_at: "2026-06-04T00:00:00",
    updated_at: "2026-06-04T11:00:00",
  }));

  api.toggleUser.mockImplementation(async (userId, isActive) => ({
    id: userId,
    username: userId === 1 ? "admin" : "operator",
    role: userId === 1 ? "admin" : "operator",
    is_active: isActive,
    last_login_at: null,
    last_login_ip: null,
    password_changed_at: null,
    created_at: "2026-06-04T00:00:00",
    updated_at: "2026-06-04T11:00:00",
  }));
}

function setupInventoryMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listDevices.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        device_uuid: "device-1",
        name: "装配边缘终端 01",
        device_sn: "SN-EDGE-001",
        project_id: 1,
        expected_profile_id: null,
        actual_profile_id: null,
        device_role: null,
        is_test_device: false,
        location: "北京",
        hardware_model: null,
        ssh_port: 10000,
        vnc_port: 10500,
        ssh_user: "root",
        ssh_auth_type: "password",
        ssh_credential_configured: true,
        local_ip: null,
        os_version: null,
        description: null,
        tags: ["视觉", "生产"],
        group_id: 1,
        status: "online",
        last_seen: null,
        created_at: "2026-05-13T00:00:00",
        updated_at: "2026-05-13T00:00:00",
      },
    ],
  });

  api.listGroups.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        name: "产线一",
        parent_id: null,
        description: "视觉终端",
        created_at: "2026-05-13T00:00:00",
        updated_at: "2026-05-13T00:00:00",
      },
    ],
  });

  api.listLogs.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        user_id: 1,
        action: "device.create",
        target_type: "device",
        target_id: 1,
        status: "success",
        detail: "SN-EDGE-001",
        created_at: "2026-05-13T00:00:00",
      },
    ],
  });
}

function setupUpdateTaskMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listUpdateTasks.mockResolvedValue({ total: 0, items: [] });

  api.previewUpdateTaskTargets.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        name: "装配边缘终端 01",
        device_sn: "SN-EDGE-001",
        project_id: 1,
        group_id: 1,
        status: "online",
        ssh_port: 10000,
        ssh_credential_configured: true,
        tags: ["视觉", "生产"],
        location: "北京",
      },
    ],
    warnings: [],
  });

  api.listUpdateTaskTemplates.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 11,
        name: "查看主机名",
        description: "只读检查",
        command: "hostname",
        task_type: "command",
        default_execution_mode: "dry_run",
        created_at: "2026-05-19T00:00:00",
        updated_at: "2026-05-19T00:00:00",
      },
    ],
  });

  api.createUpdateTaskTemplate.mockResolvedValue({
    id: 12,
    name: "新模板",
    description: null,
    command: "whoami",
    task_type: "command",
    default_execution_mode: "dry_run",
    created_at: "2026-05-19T00:00:00",
    updated_at: "2026-05-19T00:00:00",
  });

  api.updateUpdateTaskTemplate.mockResolvedValue({
    id: 11,
    name: "查看主机名",
    description: "已更新",
    command: "uptime",
    task_type: "command",
    default_execution_mode: "ssh_command",
    created_at: "2026-05-19T00:00:00",
    updated_at: "2026-05-19T00:00:00",
  });

  api.deleteUpdateTaskTemplate.mockResolvedValue(undefined);

  api.exportUpdateTaskResults.mockResolvedValue(new Blob(["task_id,status\n1,success\n"], { type: "text/csv" }));

  api.getDeviceStatus.mockResolvedValue({
    id: 1,
    status: "offline",
    last_seen: null,
  });
}

function setupAlertMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.getMonitoringOverview.mockResolvedValue({
    total_devices: 1,
    online_devices: 1,
    offline_devices: 0,
    unknown_devices: 0,
  });

  api.getAlertSummary.mockResolvedValue({
    active_count: 1,
    critical_count: 1,
    unacknowledged_count: 1,
    latest_alert_at: "2026-05-22T10:00:00",
    by_source: { metric: 1 },
    by_severity: { critical: 1 },
  });

  api.listAlerts.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 31,
        title: "CPU 高负载",
        message: "装配边缘终端 01 CPU 94% 超过阈值 85%",
        severity: "critical",
        status: "open",
        source_type: "metric",
        alert_type: "cpu_high",
        device_id: 1,
        scheduled_task_id: null,
        update_task_id: null,
        metric_name: "cpu_percent",
        metric_value: 94,
        threshold_value: 85,
        dedupe_key: "metric:cpu_high:1",
        acknowledged_by_user_id: null,
        acknowledged_at: null,
        resolved_at: null,
        note: null,
        created_at: "2026-05-22T10:00:00",
        updated_at: "2026-05-22T10:00:00",
      },
    ],
  });

  api.acknowledgeAlert.mockResolvedValue({
    id: 31,
    title: "CPU 高负载",
    message: "装配边缘终端 01 CPU 94% 超过阈值 85%",
    severity: "critical",
    status: "acknowledged",
    source_type: "metric",
    alert_type: "cpu_high",
    device_id: 1,
    scheduled_task_id: null,
    update_task_id: null,
    metric_name: "cpu_percent",
    metric_value: 94,
    threshold_value: 85,
    dedupe_key: "metric:cpu_high:1",
    acknowledged_by_user_id: 1,
    acknowledged_at: "2026-05-22T10:01:00",
    resolved_at: null,
    note: "前端确认",
    created_at: "2026-05-22T10:00:00",
    updated_at: "2026-05-22T10:01:00",
  });

  api.resolveAlert.mockResolvedValue({
    id: 31,
    title: "CPU 高负载",
    message: "装配边缘终端 01 CPU 94% 超过阈值 85%",
    severity: "critical",
    status: "resolved",
    source_type: "metric",
    alert_type: "cpu_high",
    device_id: 1,
    scheduled_task_id: null,
    update_task_id: null,
    metric_name: "cpu_percent",
    metric_value: 94,
    threshold_value: 85,
    dedupe_key: "metric:cpu_high:1",
    acknowledged_by_user_id: 1,
    acknowledged_at: "2026-05-22T10:01:00",
    resolved_at: "2026-05-22T10:02:00",
    note: "前端手动恢复",
    created_at: "2026-05-22T10:00:00",
    updated_at: "2026-05-22T10:02:00",
  });

  api.listAlertRules.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 3,
        rule_type: "cpu_high",
        enabled: true,
        severity: "warning",
        threshold_value: 85,
        window_minutes: null,
        created_at: "2026-05-22T00:00:00",
        updated_at: "2026-05-22T00:00:00",
      },
    ],
  });

  api.updateAlertRule.mockResolvedValue({
    id: 3,
    rule_type: "cpu_high",
    enabled: true,
    severity: "critical",
    threshold_value: 90,
    window_minutes: null,
    created_at: "2026-05-22T00:00:00",
    updated_at: "2026-05-22T10:00:00",
  });
}

function setupAlertChannelMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listAlertNotificationChannels.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 41,
        name: "生产告警 Webhook",
        channel_type: "webhook",
        enabled: true,
        webhook_url_preview: "https://notify.example.com/***",
        timeout_seconds: 5,
        header_keys: ["Authorization"],
        secret_configured: true,
        last_test_status: "success",
        last_test_at: "2026-05-22T10:03:00",
        last_error: null,
        created_at: "2026-05-22T00:00:00",
        updated_at: "2026-05-22T00:00:00",
      },
    ],
  });

  api.createAlertNotificationChannel.mockResolvedValue({
    id: 42,
    name: "新增 Webhook",
    channel_type: "webhook",
    enabled: true,
    webhook_url_preview: "https://notify.example.com/***",
    timeout_seconds: 5,
    header_keys: [],
    secret_configured: true,
    last_test_status: null,
    last_test_at: null,
    last_error: null,
    created_at: "2026-05-22T00:00:00",
    updated_at: "2026-05-22T00:00:00",
  });

  api.updateAlertNotificationChannel.mockResolvedValue({
    id: 41,
    name: "生产告警 Webhook",
    channel_type: "webhook",
    enabled: true,
    webhook_url_preview: "https://notify.example.com/***",
    timeout_seconds: 5,
    header_keys: ["Authorization"],
    secret_configured: true,
    last_test_status: "success",
    last_test_at: "2026-05-22T10:03:00",
    last_error: null,
    created_at: "2026-05-22T00:00:00",
    updated_at: "2026-05-22T00:00:00",
  });

  api.deleteAlertNotificationChannel.mockResolvedValue(undefined);

  api.testAlertNotificationChannel.mockResolvedValue({
    id: 41,
    name: "生产告警 Webhook",
    channel_type: "webhook",
    enabled: true,
    webhook_url_preview: "https://notify.example.com/***",
    timeout_seconds: 5,
    header_keys: ["Authorization"],
    secret_configured: true,
    last_test_status: "success",
    last_test_at: "2026-05-22T10:03:00",
    last_error: null,
    created_at: "2026-05-22T00:00:00",
    updated_at: "2026-05-22T00:00:00",
  });
}

function setupAlertPolicyMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listAlertNotificationPolicies.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 51,
        name: "严重告警触发通知",
        enabled: true,
        channel_id: 41,
        min_severity: "critical",
        source_types: [],
        alert_statuses: ["open"],
        event_types: ["triggered"],
        created_at: "2026-05-22T00:00:00",
        updated_at: "2026-05-22T00:00:00",
      },
    ],
  });

  api.createAlertNotificationPolicy.mockResolvedValue({
    id: 52,
    name: "新增策略",
    enabled: true,
    channel_id: 41,
    min_severity: "critical",
    source_types: [],
    alert_statuses: ["open"],
    event_types: ["triggered"],
    created_at: "2026-05-22T00:00:00",
    updated_at: "2026-05-22T00:00:00",
  });

  api.updateAlertNotificationPolicy.mockResolvedValue({
    id: 51,
    name: "严重告警触发通知",
    enabled: true,
    channel_id: 41,
    min_severity: "critical",
    source_types: [],
    alert_statuses: ["open"],
    event_types: ["triggered"],
    created_at: "2026-05-22T00:00:00",
    updated_at: "2026-05-22T00:00:00",
  });

  api.deleteAlertNotificationPolicy.mockResolvedValue(undefined);
}

function setupAlertDeliveryMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listAlertNotificationDeliveries.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 61,
        alert_id: 31,
        channel_id: 41,
        policy_id: 51,
        event_type: "triggered",
        status: "failed",
        attempt_count: 1,
        last_attempt_at: "2026-05-22T10:04:00",
        next_retry_at: "2026-05-22T10:05:00",
        response_status_code: 500,
        response_summary: null,
        error_message: "服务端错误",
        alert_title: "CPU 高负载",
        channel_name: "生产告警 Webhook",
        policy_name: "严重告警触发通知",
        created_at: "2026-05-22T10:04:00",
        updated_at: "2026-05-22T10:04:00",
      },
    ],
  });

  api.retryAlertNotificationDelivery.mockResolvedValue({
    id: 61,
    alert_id: 31,
    channel_id: 41,
    policy_id: 51,
    event_type: "triggered",
    status: "success",
    attempt_count: 2,
    last_attempt_at: "2026-05-22T10:06:00",
    next_retry_at: null,
    response_status_code: 200,
    response_summary: "ok",
    error_message: null,
    alert_title: "CPU 高负载",
    channel_name: "生产告警 Webhook",
    policy_name: "严重告警触发通知",
    created_at: "2026-05-22T10:04:00",
    updated_at: "2026-05-22T10:06:00",
  });

  api.getAlertNotificationSummary.mockResolvedValue({
    enabled_channel_count: 1,
    enabled_policy_count: 1,
    failed_delivery_count: 1,
    retrying_delivery_count: 0,
    last_delivery_at: "2026-05-22T10:04:00",
    warnings: ["存在 1 条失败通知投递"],
  });
}

function setupMetricsAndFileMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listDeviceMetrics.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        device_id: 1,
        status: "online",
        cpu_percent: 64,
        memory_percent: 72,
        disk_percent: 81,
        recorded_at: new Date().toISOString(),
      },
    ],
  });

  api.changePassword.mockResolvedValue(undefined);

  api.exportLogs.mockResolvedValue(new Blob(["id,action\n1,device.create\n"], { type: "text/csv" }));

  api.listDeviceFiles.mockResolvedValue({
    device_id: 1,
    path: "/",
    items: [
      {
        name: "config.bin",
        path: "/config.bin",
        type: "file",
        size: 4,
        modified_at: "2026-05-19T00:00:00",
      },
      {
        name: "logs",
        path: "/logs",
        type: "directory",
        size: 0,
        modified_at: null,
      },
    ],
  });

  api.uploadDeviceFile.mockResolvedValue({
    device_id: 1,
    remote_path: "/payload.bin",
    status: "uploaded",
    size: 4,
  });

  api.downloadDeviceFile.mockResolvedValue(new Blob([new Uint8Array([0, 1, 2, 255])], { type: "application/octet-stream" }));

  api.deleteDeviceFile.mockResolvedValue({
    device_id: 1,
    remote_path: "/config.bin",
    status: "deleted",
    size: null,
  });
}

function setupScheduledTaskMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.listScheduledTasks.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 7,
        name: "巡检任务",
        task_type: "command",
        schedule: "interval:300",
        command: "hostname",
        target_filter: { project_id: "frps-import" },
        enabled: true,
        execution_mode: "dry_run",
        failure_strategy: "continue",
        concurrency_limit: 5,
        last_run_at: "2026-05-19T00:00:00",
        last_status: "success",
        last_error: null,
        next_run_at: "2026-05-19T00:05:00",
        running: false,
        created_at: "2026-05-19T00:00:00",
        updated_at: "2026-05-19T00:00:00",
      },
    ],
  });

  api.createScheduledTask.mockResolvedValue({
    id: 8,
    name: "新建巡检",
    task_type: "command",
    schedule: "interval:600",
    command: "whoami",
    target_filter: { project_id: "frps-import" },
    enabled: true,
    execution_mode: "dry_run",
    failure_strategy: "continue",
    concurrency_limit: 5,
    last_run_at: null,
    last_status: null,
    last_error: null,
    next_run_at: "2026-05-19T00:10:00",
    running: false,
    created_at: "2026-05-19T00:00:00",
    updated_at: "2026-05-19T00:00:00",
  });

  api.updateScheduledTask.mockResolvedValue({
    id: 7,
    name: "巡检任务已更新",
    task_type: "command",
    schedule: "interval:300",
    command: "hostname",
    target_filter: { project_id: "frps-import" },
    enabled: true,
    execution_mode: "dry_run",
    failure_strategy: "continue",
    concurrency_limit: 5,
    last_run_at: "2026-05-19T00:00:00",
    last_status: "success",
    last_error: null,
    next_run_at: "2026-05-19T00:05:00",
    running: false,
    created_at: "2026-05-19T00:00:00",
    updated_at: "2026-05-19T00:00:00",
  });

  api.deleteScheduledTask.mockResolvedValue(undefined);

  api.toggleScheduledTask.mockResolvedValue({
    id: 7,
    name: "巡检任务",
    task_type: "command",
    schedule: "interval:300",
    command: "hostname",
    target_filter: { project_id: "frps-import" },
    enabled: false,
    execution_mode: "dry_run",
    failure_strategy: "continue",
    concurrency_limit: 5,
    last_run_at: "2026-05-19T00:00:00",
    last_status: "success",
    last_error: null,
    next_run_at: null,
    running: false,
    created_at: "2026-05-19T00:00:00",
    updated_at: "2026-05-19T00:00:00",
  });

  api.executeScheduledTask.mockResolvedValue({
    task_id: 7,
    status: "success",
    output_summary: "simulated scheduled task execution: hostname",
    run_id: 10,
  });

  api.runScheduledTaskNow.mockResolvedValue({
    task_id: 7,
    status: "success",
    output_summary: "simulated scheduled task execution: hostname",
    run_id: 11,
  });

  api.listScheduledTaskRuns.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 11,
        scheduled_task_id: 7,
        trigger_type: "manual",
        status: "success",
        started_at: "2026-05-19T00:00:00",
        finished_at: "2026-05-19T00:00:02",
        duration_ms: 2000,
        output_summary: "simulated scheduled task execution: hostname",
        error_message: null,
        created_update_task_id: 18,
        created_at: "2026-05-19T00:00:00",
      },
    ],
  });

  api.getSchedulerStatus.mockResolvedValue({
    enabled: true,
    running: true,
    poll_interval_seconds: 30,
    last_scan_at: "2026-05-19T00:00:00",
    last_error: null,
    job_count: 1,
  });

  api.listScheduledTaskLogs.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 10,
        user_id: 1,
        action: "scheduled_task.execute",
        target_type: "scheduled_task",
        target_id: 7,
        status: "success",
        detail: "simulated scheduled task execution: hostname",
        created_at: "2026-05-19T00:00:00",
      },
    ],
  });
}

function setupDiagnosticsMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.getDiagnosticsConfig.mockResolvedValue({
    service_name: "edge-platform",
    version: "0.1.0",
    api_prefix: "/api",
    database: "sqlite:///edge-platform.db",
    file_backend: "local",
    remote_gateway_host: "127.0.0.1",
    vnc_gateway_host: "127.0.0.1",
    ssh_timeout_seconds: 15,
    vnc_timeout_seconds: 15,
    default_device_ssh_user: "ztl",
    security: {
      credential_encryption_configured: false,
      jwt_secret_configured: false,
      default_admin_password_in_use: false,
      default_device_ssh_password_in_use: true,
      warnings: ["未配置设备凭据加密密钥"],
    },
    migration: {
      current_revision: "20260511_0001",
      head_revision: "20260511_0001",
      has_pending_migrations: false,
      last_error: null,
    },
    ssh_host_key: {
      policy: "auto_add",
      known_hosts_configured: false,
      warnings: ["SSH 主机密钥策略为 auto_add"],
    },
    auth_lifetime: {
      access_expire_minutes: 30,
      refresh_expire_minutes: 43200,
      jwt_secret_configured: false,
    },
    database_status: {
      summary: "sqlite:///edge-platform.db",
      sqlite_backup_recommended: true,
    },
    scheduler: {
      enabled: true,
      running: true,
      poll_interval_seconds: 30,
      last_scan_at: "2026-05-19T00:00:00",
      last_error: null,
      enabled_task_count: 1,
      failed_run_count: 0,
      warnings: [],
    },
    alerts: {
      active_count: 1,
      critical_count: 1,
      latest_alert_at: "2026-05-22T10:00:00",
      warnings: ["存在 1 条严重告警"],
    },
    notifications: {
      enabled_channel_count: 1,
      enabled_policy_count: 1,
      failed_delivery_count: 1,
      retrying_delivery_count: 0,
      warnings: ["存在 1 条失败通知投递"],
    },
    users: {
      total_count: 2,
      active_count: 2,
      admin_count: 1,
      operator_count: 1,
      disabled_count: 0,
      warnings: [],
    },
    system_settings: {
      table_available: true,
      database_override_count: 0,
      pending_restart_count: 0,
      credential_encryption_configured: false,
      systemd_managed: false,
      invalid_override_count: 0,
      warnings: ["当前未检测到 systemd 托管，系统设置重启按钮不可用"],
    },
  });
}

function setupSystemSettingSchemaMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.getSystemSettingSchema.mockResolvedValue({
    groups: {
      remote_connection: "远程连接",
      device_credentials: "默认设备凭据",
      file_storage: "文件与存储",
      scheduler: "调度器",
      alert_notification: "告警通知",
      security_auth: "安全与认证",
      readonly_status: "只读状态",
    },
    items: [
      {
        key: "REMOTE_GATEWAY_HOST",
        name: "SSH 网关主机",
        description: "远程 SSH 网关主机地址",
        category: "remote_connection",
        value_type: "string",
        editable: true,
        secret: false,
        requires_restart: false,
        runtime_effective: true,
        options: null,
        min_value: null,
        max_value: null,
      },
      {
        key: "DEFAULT_VNC_PASSWORD",
        name: "默认 VNC 密码",
        description: "远程 VNC 连接默认使用的密码，可在连接页临时覆盖",
        category: "remote_connection",
        value_type: "string",
        editable: true,
        secret: true,
        requires_restart: false,
        runtime_effective: true,
        options: null,
        min_value: null,
        max_value: null,
      },
      {
        key: "DEFAULT_DEVICE_SSH_PASSWORD",
        name: "默认 SSH 密码",
        description: "自动导入设备时使用的默认 SSH 密码",
        category: "device_credentials",
        value_type: "string",
        editable: true,
        secret: true,
        requires_restart: false,
        runtime_effective: true,
        options: null,
        min_value: null,
        max_value: null,
      },
      {
        key: "FILE_STORAGE_DIR",
        name: "文件存储目录",
        description: "本地文件后端存储目录",
        category: "file_storage",
        value_type: "string",
        editable: true,
        secret: false,
        requires_restart: true,
        runtime_effective: false,
        options: null,
        min_value: null,
        max_value: null,
      },
      {
        key: "CREDENTIAL_ENCRYPTION_KEY",
        name: "凭据加密密钥",
        description: "启动级敏感凭据加密密钥状态",
        category: "readonly_status",
        value_type: "string",
        editable: false,
        secret: true,
        requires_restart: false,
        runtime_effective: true,
        options: null,
        min_value: null,
        max_value: null,
      },
    ],
  });
}

function setupEffectiveSystemSettingMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.getEffectiveSystemSettings.mockResolvedValue({
    pending_restart_count: 0,
    database_override_count: 0,
    credential_encryption_configured: false,
    systemd_managed: false,
    items: [
      {
        key: "REMOTE_GATEWAY_HOST",
        name: "SSH 网关主机",
        category: "remote_connection",
        value_type: "string",
        value: "127.0.0.1",
        configured: true,
        source: "default",
        editable: true,
        secret: false,
        requires_restart: false,
        pending_restart: false,
        is_valid: true,
        invalid_reason: null,
        updated_at: null,
      },
      {
        key: "DEFAULT_VNC_PASSWORD",
        name: "默认 VNC 密码",
        category: "remote_connection",
        value_type: "string",
        value: null,
        configured: false,
        source: "default",
        editable: true,
        secret: true,
        requires_restart: false,
        pending_restart: false,
        is_valid: true,
        invalid_reason: null,
        updated_at: null,
      },
      {
        key: "DEFAULT_DEVICE_SSH_PASSWORD",
        name: "默认 SSH 密码",
        category: "device_credentials",
        value_type: "string",
        value: null,
        configured: true,
        source: "default",
        editable: true,
        secret: true,
        requires_restart: false,
        pending_restart: false,
        is_valid: true,
        invalid_reason: null,
        updated_at: null,
      },
      {
        key: "FILE_STORAGE_DIR",
        name: "文件存储目录",
        category: "file_storage",
        value_type: "string",
        value: null,
        configured: false,
        source: "default",
        editable: true,
        secret: false,
        requires_restart: true,
        pending_restart: false,
        is_valid: true,
        invalid_reason: null,
        updated_at: null,
      },
      {
        key: "CREDENTIAL_ENCRYPTION_KEY",
        name: "凭据加密密钥",
        category: "readonly_status",
        value_type: "string",
        value: null,
        configured: false,
        source: "default",
        editable: false,
        secret: true,
        requires_restart: false,
        pending_restart: false,
        is_valid: true,
        invalid_reason: null,
        updated_at: null,
      },
    ],
  });
}

function setupSystemSettingActionMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.updateSystemSettingGroup.mockImplementation(async (group, values) => ({
    group,
    updated_keys: Object.keys(values),
    requires_restart: group === "file_storage",
    pending_restart_count: group === "file_storage" ? 1 : 0,
    items: [
      {
        key: "REMOTE_GATEWAY_HOST",
        name: "SSH 网关主机",
        category: "remote_connection",
        value_type: "string",
        value: typeof values.REMOTE_GATEWAY_HOST === "string" ? values.REMOTE_GATEWAY_HOST : "127.0.0.1",
        configured: true,
        source: values.REMOTE_GATEWAY_HOST ? "database" : "default",
        editable: true,
        secret: false,
        requires_restart: false,
        pending_restart: false,
        is_valid: true,
        invalid_reason: null,
        updated_at: "2026-06-10T00:00:00",
      },
      {
        key: "FILE_STORAGE_DIR",
        name: "文件存储目录",
        category: "file_storage",
        value_type: "string",
        value: typeof values.FILE_STORAGE_DIR === "string" ? values.FILE_STORAGE_DIR : null,
        configured: typeof values.FILE_STORAGE_DIR === "string" && values.FILE_STORAGE_DIR.length > 0,
        source: typeof values.FILE_STORAGE_DIR === "string" && values.FILE_STORAGE_DIR.length > 0 ? "database" : "default",
        editable: true,
        secret: false,
        requires_restart: true,
        pending_restart: group === "file_storage",
        is_valid: true,
        invalid_reason: null,
        updated_at: "2026-06-10T00:00:00",
      },
    ],
  }));

  api.resetSystemSetting.mockResolvedValue({
    key: "REMOTE_GATEWAY_HOST",
    source: "system",
    requires_restart: false,
    pending_restart_count: 0,
  });

  api.listSystemSettingChanges.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        setting_key: "REMOTE_GATEWAY_HOST",
        category: "remote_connection",
        action: "save",
        old_source: "default",
        new_source: "database",
        old_value_snapshot: "127.0.0.1",
        new_value_snapshot: "10.0.0.8",
        is_secret: false,
        requires_restart: false,
        pending_restart_after_change: false,
        actor_user_id: 1,
        actor_username: "admin",
        client_ip: "127.0.0.1",
        created_at: "2026-06-10T00:00:00",
      },
    ],
  });

  api.restartSystemService.mockResolvedValue({ status: "restarting", message: "服务正在重启" });
}

function setupRemoteAndFrpsMocks(api: PlatformApiMock, health: HealthApiMock) {
  api.syncDeviceConfig.mockResolvedValue({
    device_id: 1,
    status: "generated",
    config: "[common]\nserver_addr = 127.0.0.1\n",
  });

  api.openSshSession.mockResolvedValue({
    device_id: 1,
    session_type: "ssh",
    status: "ready",
    remote_port: 10000,
    websocket_url: "/api/ws/devices/1/ssh",
    proxy_url: null,
  });

  api.openVncSession.mockResolvedValue({
    device_id: 1,
    session_type: "vnc",
    status: "ready",
    remote_port: 10500,
    websocket_url: "/api/ws/devices/1/vnc",
    proxy_url: null,
  });

  api.importFrpsDevices.mockResolvedValue({
    total: 2,
    created: 2,
    skipped: 0,
    synced: 0,
    conflicts: 0,
    items: [
      {
        name: "frps-12008",
        device_sn: "frps-12008",
        project_id: 1,
        ssh_port: 12008,
        vnc_port: 17008,
        ssh_proxy_name: "ssh-12008",
        vnc_proxy_name: "vnc-17008",
        status: "online",
        import_status: "created",
        detail: "已导入设备 2",
        existing_device_id: 2,
      },
    ],
  });
}

export function mockResolvedApiState(api: PlatformApiMock, health: HealthApiMock) {
  setupHealthAndAuthMocks(api, health);
  setupUserMocks(api, health);
  setupInventoryMocks(api, health);
  setupUpdateTaskMocks(api, health);
  setupAlertMocks(api, health);
  setupAlertChannelMocks(api, health);
  setupAlertPolicyMocks(api, health);
  setupAlertDeliveryMocks(api, health);
  setupMetricsAndFileMocks(api, health);
  setupScheduledTaskMocks(api, health);
  setupDiagnosticsMocks(api, health);
  setupSystemSettingSchemaMocks(api, health);
  setupEffectiveSystemSettingMocks(api, health);
  setupSystemSettingActionMocks(api, health);
  setupRemoteAndFrpsMocks(api, health);
}
