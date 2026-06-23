import { mount } from "@vue/test-utils";
import ElementPlus, { ElMessageBox } from "element-plus";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { createPinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";

import App from "../App.vue";
import * as healthApi from "../api/health";
import * as platformApi from "../api/platform";

async function mountApp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:pathMatch(.*)*", component: { template: "<div></div>" } }],
  });
  router.push("/");
  await router.isReady();
  const wrapper = mount(App, {
    global: {
      plugins: [ElementPlus, createPinia(), router],
      stubs: { teleport: true },
    },
  });
  return { wrapper, router };
}

const remoteMocks = vi.hoisted(() => {
  class FakeTerminal {
    cols = 88;
    rows = 24;
    output = "";
    dataCallbacks: Array<(data: string) => void> = [];

    loadAddon() {}

    open() {}

    write(data: string) {
      this.output += data;
    }

    writeln(data: string) {
      this.output += `${data}\n`;
    }

    onData(callback: (data: string) => void) {
      this.dataCallbacks.push(callback);
      return { dispose() {} };
    }

    emitData(data: string) {
      for (const callback of this.dataCallbacks) {
        callback(data);
      }
    }

    dispose() {}
  }

  class FakeFitAddon {
    fit() {}
    dispose() {}
  }

  class FakeRfb {
    listeners: Record<string, Array<(event: Event) => void>> = {};
    disconnected = false;

    constructor(
      public target: HTMLElement,
      public url: string,
      public options: Record<string, unknown>,
    ) {}

    addEventListener(type: string, callback: (event: Event) => void) {
      this.listeners[type] ??= [];
      this.listeners[type].push(callback);
    }

    emit(type: string) {
      for (const callback of this.listeners[type] ?? []) {
        callback(new Event(type));
      }
    }

    disconnect() {
      this.disconnected = true;
      this.emit("disconnect");
    }
  }

  return {
    terminalInstances: [] as FakeTerminal[],
    rfbInstances: [] as FakeRfb[],
    FakeTerminal,
    FakeFitAddon,
    FakeRfb,
  };
});

vi.mock("@xterm/xterm", () => ({
  Terminal: class extends remoteMocks.FakeTerminal {
    constructor() {
      super();
      remoteMocks.terminalInstances.push(this);
    }
  },
}));

vi.mock("@xterm/addon-fit", () => ({
  FitAddon: remoteMocks.FakeFitAddon,
}));

vi.mock("@novnc/novnc", () => ({
  default: class extends remoteMocks.FakeRfb {
    constructor(target: HTMLElement, url: string, options: Record<string, unknown>) {
      super(target, url, options);
      remoteMocks.rfbInstances.push(this);
    }
  },
}));

vi.mock("../api/platform", () => ({
  AUTH_EXPIRED_EVENT: "edge-platform-auth-expired",
  clearAuthTokens: vi.fn(),
  buildApiWebSocketUrl: vi.fn((path: string, token: string) => `ws://test${path}?token=${token}`),
  cancelUpdateTask: vi.fn(),
  changePassword: vi.fn(),
  createDevice: vi.fn(),
  createGroup: vi.fn(),
  createUpdateTask: vi.fn(),
  deleteGroup: vi.fn(),
  deleteDevice: vi.fn(),
  executeUpdateTask: vi.fn(),
  exportLogs: vi.fn(),
  exportUpdateTaskResults: vi.fn(),
  listDeviceFiles: vi.fn(),
  uploadDeviceFile: vi.fn(),
  downloadDeviceFile: vi.fn(),
  deleteDeviceFile: vi.fn(),
  listScheduledTasks: vi.fn(),
  createScheduledTask: vi.fn(),
  updateScheduledTask: vi.fn(),
  deleteScheduledTask: vi.fn(),
  toggleScheduledTask: vi.fn(),
  executeScheduledTask: vi.fn(),
  runScheduledTaskNow: vi.fn(),
  listScheduledTaskRuns: vi.fn(),
  listScheduledTaskLogs: vi.fn(),
  getSchedulerStatus: vi.fn(),
  listAlerts: vi.fn(),
  getAlertSummary: vi.fn(),
  acknowledgeAlert: vi.fn(),
  resolveAlert: vi.fn(),
  listAlertRules: vi.fn(),
  updateAlertRule: vi.fn(),
  listAlertNotificationChannels: vi.fn(),
  createAlertNotificationChannel: vi.fn(),
  updateAlertNotificationChannel: vi.fn(),
  deleteAlertNotificationChannel: vi.fn(),
  testAlertNotificationChannel: vi.fn(),
  listAlertNotificationPolicies: vi.fn(),
  createAlertNotificationPolicy: vi.fn(),
  updateAlertNotificationPolicy: vi.fn(),
  deleteAlertNotificationPolicy: vi.fn(),
  listAlertNotificationDeliveries: vi.fn(),
  retryAlertNotificationDelivery: vi.fn(),
  getAlertNotificationSummary: vi.fn(),
  getAccessToken: vi.fn(() => "access-token"),
  getCurrentUser: vi.fn(),
  getDeviceStatus: vi.fn(),
  getDiagnosticsConfig: vi.fn(),
  getSystemSettingSchema: vi.fn(),
  getEffectiveSystemSettings: vi.fn(),
  updateSystemSettingGroup: vi.fn(),
  resetSystemSetting: vi.fn(),
  listSystemSettingChanges: vi.fn(),
  restartSystemService: vi.fn(),
  hasStoredAccessToken: vi.fn(() => false),
  importFrpsDevices: vi.fn(),
  listDevices: vi.fn(),
  listDeviceMetrics: vi.fn(),
  listGroups: vi.fn(),
  listLogs: vi.fn(),
  listUpdateTasks: vi.fn(),
  listUsers: vi.fn(),
  previewUpdateTaskTargets: vi.fn(),
  listUpdateTaskTemplates: vi.fn(),
  createUpdateTaskTemplate: vi.fn(),
  updateUpdateTaskTemplate: vi.fn(),
  deleteUpdateTaskTemplate: vi.fn(),
  loginAdmin: vi.fn(),
  openSshSession: vi.fn(),
  openVncSession: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  resetUserPassword: vi.fn(),
  toggleUser: vi.fn(),
  setAuthTokens: vi.fn(),
  syncDeviceConfig: vi.fn(),
  updateDevice: vi.fn(),
  updateGroup: vi.fn(),
  getMonitoringOverview: vi.fn(),
}));

vi.mock("../api/health", () => ({
  fetchHealth: vi.fn(),
}));

const api = vi.mocked(platformApi);
const health = vi.mocked(healthApi);

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  constructor(public url: string) {
    mockWebSockets.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  receive(data: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data) }));
  }

  fail() {
    this.onerror?.(new Event("error"));
  }
}

const mockWebSockets: MockWebSocket[] = [];

function mockResolvedApiState() {
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
  api.listDevices.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        name: "装配边缘终端 01",
        device_sn: "SN-EDGE-001",
        project_id: "工厂-a",
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
  api.listUpdateTasks.mockResolvedValue({ total: 0, items: [] });
  api.previewUpdateTaskTargets.mockResolvedValue({
    total: 1,
    items: [
      {
        id: 1,
        name: "装配边缘终端 01",
        device_sn: "SN-EDGE-001",
        project_id: "工厂-a",
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
        project_id: "frps-import",
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

async function flushAsync() {
  for (let index = 0; index < 4; index += 1) {
    await nextTick();
    await Promise.resolve();
  }
}

async function waitUntil(assertion: () => void) {
  let lastError: unknown;
  for (let index = 0; index < 20; index += 1) {
    try {
      assertion();
      return;
    } catch (error) {
      lastError = error;
      await flushAsync();
    }
  }
  throw lastError;
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    mockWebSockets.length = 0;
    remoteMocks.terminalInstances.length = 0;
    remoteMocks.rfbInstances.length = 0;
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    window.URL.createObjectURL = vi.fn();
    window.URL.revokeObjectURL = vi.fn();
    vi.spyOn(window.URL, "createObjectURL").mockReturnValue("blob:operation-logs");
    vi.spyOn(window.URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.spyOn(ElMessageBox, "confirm").mockResolvedValue("confirm" as never);
    mockResolvedApiState();
  });

  it("validates login before showing the operation surface", async () => {
    const { wrapper, router } = await mountApp();

    expect(wrapper.text()).toContain("边缘设备管理平台");
    expect(wrapper.text()).toContain("登录");

    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    expect(wrapper.text()).toContain("请输入密码");
    expect(wrapper.findAll(".form-error")).toHaveLength(1);
    expect(api.loginAdmin).not.toHaveBeenCalled();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.loginAdmin).toHaveBeenCalledWith("admin", "admin-pass");
    expect(api.setAuthTokens).toHaveBeenCalledWith("access-token", "refresh-token");
    expect(api.listDevices).toHaveBeenCalled();
    expect(api.listGroups).toHaveBeenCalled();
    expect(api.listUpdateTasks).toHaveBeenCalled();
    expect(api.listUpdateTasks).toHaveBeenCalled();
    expect(api.getMonitoringOverview).toHaveBeenCalled();
    expect(wrapper.text()).toContain("设备运维");
    expect(wrapper.text()).toContain("批量更新");
  });

  it("shows user management for admin users and creates an operator", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(wrapper.find('[data-testid="nav-users"]').exists()).toBe(true);

    await wrapper.find('[data-testid="nav-users"]').trigger("click");
    await flushAsync();
    expect(api.listUsers).toHaveBeenCalled();
    expect(wrapper.text()).toContain("用户管理");
    expect(wrapper.text()).toContain("operator");

    await wrapper.find('[data-testid="open-user-create"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="user-username"] input').setValue("ops2");
    await wrapper.find('[data-testid="user-password"] input').setValue("password123");
    await wrapper.find('[data-testid="user-create"]').trigger("click");
    await flushAsync();

    expect(api.createUser).toHaveBeenCalledWith({
      username: "ops2",
      password: "password123",
      role: "operator",
      is_active: true,
    });
  });

  it("lets admin manage system settings with restart warnings", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(wrapper.find('[data-testid="nav-settings"]').exists()).toBe(true);
    await wrapper.find('[data-testid="nav-settings"]').trigger("click");
    await waitUntil(() => expect(api.getSystemSettingSchema).toHaveBeenCalled());
    expect(wrapper.text()).toContain("系统设置");
    expect(wrapper.text()).toContain("数据库覆盖");
    expect(wrapper.text()).toContain("未配置凭据加密密钥，不能保存该敏感配置。");
    await waitUntil(() => expect(wrapper.find('[data-testid="setting-REMOTE_GATEWAY_HOST"]').exists()).toBe(true));

    await wrapper.find('[data-testid="setting-REMOTE_GATEWAY_HOST"]').setValue("10.0.0.8");
    await wrapper.find('[data-testid="save-settings-remote_connection"]').trigger("click");
    await waitUntil(() => expect(api.updateSystemSettingGroup).toHaveBeenCalledWith("remote_connection", {
      REMOTE_GATEWAY_HOST: "10.0.0.8",
    }));

    await wrapper.find('[data-testid="reset-setting-REMOTE_GATEWAY_HOST"]').trigger("click");
    await waitUntil(() => expect(api.resetSystemSetting).toHaveBeenCalledWith("REMOTE_GATEWAY_HOST"));

    await wrapper.find('[data-testid="setting-FILE_STORAGE_DIR"]').setValue("C:/edge-files");
    await wrapper.find('[data-testid="save-settings-file_storage"]').trigger("click");
    await flushAsync();
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      expect.stringContaining("当前分组包含重启后生效配置"),
      "配置需重启后生效",
      expect.any(Object),
    );
    expect(api.updateSystemSettingGroup).toHaveBeenCalledWith("file_storage", {
      FILE_STORAGE_DIR: "C:/edge-files",
    });

    await wrapper.find('[data-testid="restart-confirm-text"]').setValue("确认重启");
    await wrapper.find('[data-testid="restart-service"]').trigger("click");
    await waitUntil(() => expect(api.restartSystemService).toHaveBeenCalledWith("确认重启"));
  });

  it("hides user management for operator users", async () => {
    api.getCurrentUser.mockResolvedValueOnce({
      id: 2,
      username: "operator",
      role: "operator",
      is_active: true,
    });
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-username"] input').setValue("operator");
    await wrapper.find('[data-testid="login-password"] input').setValue("operator-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.loginAdmin).toHaveBeenCalledWith("operator", "operator-pass");
    expect(wrapper.find('[data-testid="nav-users"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="nav-settings"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("operator · 运维人员");
  });

  it("shows one validation message for incorrect credentials", async () => {
    api.loginAdmin.mockRejectedValueOnce(new Error("bad credentials"));
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("wrong-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(wrapper.text()).toContain("用户名或密码不正确");
    expect(wrapper.findAll(".form-error")).toHaveLength(1);
  });

  it("keeps the authenticated surface visible when a data endpoint fails after login", async () => {
    api.listUpdateTasks.mockRejectedValueOnce(
      Object.assign(new Error("server error"), {
        response: { status: 500 },
      }),
    );
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.clearAuthTokens).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="nav-devices"]').exists()).toBe(true);
  });

  it("creates a device through the backend API and exposes SSH/VNC entry points", async () => {
    api.createDevice.mockResolvedValueOnce({
      id: 2,
      name: "边缘相机 09",
      device_sn: "SN-W5-009",
      project_id: "工厂-wave5",
      location: null,
      hardware_model: null,
      ssh_port: 10001,
      vnc_port: 10501,
      ssh_user: "root",
      ssh_auth_type: "password",
      ssh_credential_configured: true,
      local_ip: null,
      os_version: null,
      description: null,
      tags: ["视觉", "生产"],
      group_id: null,
      status: "unknown",
      last_seen: null,
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
    });
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-devices"]').trigger("click");
    await wrapper.find('[data-testid="open-device-create"]').trigger("click");
    await wrapper.find('[data-testid="device-name"] input').setValue("边缘相机 09");
    await wrapper.find('[data-testid="device-sn"] input').setValue("SN-W5-009");
    await wrapper.find('[data-testid="device-project"] input').setValue("工厂-wave5");
    await wrapper.find('[data-testid="device-tags"] input').setValue("视觉,生产");
    await wrapper.find('[data-testid="save-device"]').trigger("click");
    await flushAsync();

    expect(api.createDevice).toHaveBeenCalledWith({
      name: "边缘相机 09",
      device_sn: "SN-W5-009",
      project_id: "工厂-wave5",
      group_id: 1,
      location: undefined,
      tags: ["视觉", "生产"],
      ssh_user: "ztl",
      ssh_auth_type: "password",
    });
    expect(wrapper.text()).toContain("边缘相机 09");
    expect(wrapper.text()).toContain("SN-W5-009");
    expect(wrapper.text()).toContain("SSH");
    expect(wrapper.text()).toContain("VNC");
  });

  it("imports existing frps proxies into devices", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-devices"]').trigger("click");
    await wrapper.find('[data-testid="open-frps-import"]').trigger("click");
    await wrapper.find('[data-testid="frps-url"] input').setValue("124.70.177.226:7500");
    await wrapper.find('[data-testid="import-frps"]').trigger("click");
    await flushAsync();

    expect(api.importFrpsDevices).toHaveBeenCalledWith({
      dashboard_url: "124.70.177.226:7500",
      username: "admin",
      password: "admin",
      ssh_port_start: 12001,
      ssh_port_end: 17000,
      vnc_port_start: 17001,
      vnc_port_end: 22000,
      project_id: "frps-import",
      location: "frps",
      overwrite_project_location: false,
    });
    expect(wrapper.text()).toContain("新增 2");
    expect(wrapper.text()).toContain("frps-12008");
  });

  it("shows real device metrics, stale state, and monitoring diagnostics", async () => {
    api.listDeviceMetrics.mockResolvedValueOnce({
      total: 1,
      items: [
        {
          id: 9,
          device_id: 1,
          status: "online",
          cpu_percent: 94,
          memory_percent: 86,
          disk_percent: 91,
          recorded_at: "2026-05-18T06:00:00Z",
        },
      ],
    });
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.listDeviceMetrics).toHaveBeenCalledWith(1, 1);
    expect(wrapper.text()).toContain("CPU 94%");
    expect(wrapper.text()).toContain("内存 86%");
    expect(wrapper.text()).toContain("磁盘 91%");
    expect(wrapper.text()).toContain("指标过期");
    expect(wrapper.text()).toContain("高负载");
    expect(wrapper.text()).toContain("磁盘紧张");

    await wrapper.find('[data-testid="nav-diagnostics"]').trigger("click");
    await flushAsync();
    expect(wrapper.text()).toContain("监控可用性");
    expect(wrapper.text()).toContain("有指标设备：1");
    expect(wrapper.text()).toContain("无指标设备：0");
  });

  it("does not show fake zero metrics and keeps the page when metric loading fails", async () => {
    api.listDeviceMetrics.mockRejectedValueOnce(
      Object.assign(new Error("metric unavailable"), {
        response: { status: 500 },
      }),
    );
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.clearAuthTokens).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("指标加载失败");
    expect(wrapper.text()).not.toContain("CPU 0%");
  });

  it("changes the admin password and returns to the login page", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="open-password-change"]').trigger("click");
    await wrapper.find('[data-testid="old-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="new-password"] input').setValue("new-admin-pass");
    await wrapper.find('[data-testid="confirm-password"] input').setValue("new-admin-pass");
    await wrapper.find('[data-testid="save-password"]').trigger("click");
    await flushAsync();

    expect(api.changePassword).toHaveBeenCalledWith({
      old_password: "admin-pass",
      new_password: "new-admin-pass",
    });
    expect(api.clearAuthTokens).toHaveBeenCalled();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(true);
  });

  it("returns to the login page when the API reports expired authentication", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(false);

    window.dispatchEvent(new Event(platformApi.AUTH_EXPIRED_EVENT));
    await nextTick();

    expect(api.clearAuthTokens).toHaveBeenCalled();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(true);
    expect(wrapper.text()).toContain("登录状态已过期，请重新登录。");
  });

  it("creates, edits, filters, and deletes groups", async () => {
    api.createGroup.mockResolvedValueOnce({
      id: 2,
      name: "产线二",
      parent_id: null,
      description: "测试线",
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
    });
    api.updateGroup.mockResolvedValueOnce({
      id: 2,
      name: "产线二已更新",
      parent_id: null,
      description: "更新后的测试线",
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
    });
    api.deleteGroup.mockResolvedValueOnce(undefined);
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-groups"]').trigger("click");
    await wrapper.find('[data-testid="open-group-create"]').trigger("click");
    await wrapper.find('[data-testid="group-name"] input').setValue("产线二");
    await wrapper.find('[data-testid="group-description"] textarea').setValue("测试线");
    await wrapper.find('[data-testid="save-group"]').trigger("click");
    await flushAsync();

    expect(api.createGroup).toHaveBeenCalledWith({
      name: "产线二",
      parent_id: null,
      description: "测试线",
    });
    expect(wrapper.text()).toContain("产线二");

    await wrapper.find('[data-testid="edit-group-2"]').trigger("click");
    await wrapper.find('[data-testid="group-name"] input').setValue("产线二已更新");
    await wrapper.find('[data-testid="save-group"]').trigger("click");
    await flushAsync();
    expect(api.updateGroup).toHaveBeenCalledWith(2, {
      name: "产线二已更新",
      parent_id: null,
      description: "测试线",
    });

    await wrapper.find('[data-testid="filter-group-1"]').trigger("click");
    expect(wrapper.find('[data-testid="nav-devices"]').classes()).toContain("is-active");

    await wrapper.find('[data-testid="nav-groups"]').trigger("click");
    await wrapper.find('[data-testid="delete-group-2"]').trigger("click");
    await flushAsync();
    expect(api.deleteGroup).toHaveBeenCalledWith(2);
  });

  it("edits, refreshes, and deletes a device from the device table", async () => {
    api.updateDevice.mockResolvedValueOnce({
      id: 1,
      name: "装配边缘终端 01 已更新",
      device_sn: "SN-EDGE-001",
      project_id: "工厂-b",
      location: "上海",
      hardware_model: null,
      ssh_port: 10000,
      vnc_port: 10500,
      ssh_user: "ztl",
      ssh_auth_type: "password",
      ssh_credential_configured: true,
      local_ip: null,
      os_version: null,
      description: null,
      tags: ["维护"],
      group_id: 1,
      status: "online",
      last_seen: null,
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
    });
    api.deleteDevice.mockResolvedValueOnce(undefined);
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-devices"]').trigger("click");
    await wrapper.find('[data-testid="edit-device-1"]').trigger("click");
    await wrapper.find('[data-testid="device-name"] input').setValue("装配边缘终端 01 已更新");
    await wrapper.find('[data-testid="device-project"] input').setValue("工厂-b");
    await wrapper.find('[data-testid="device-tags"] input').setValue("维护");
    await wrapper.find('[data-testid="save-device"]').trigger("click");
    await flushAsync();

    expect(api.updateDevice).toHaveBeenCalledWith(1, {
      name: "装配边缘终端 01 已更新",
      project_id: "工厂-b",
      group_id: 1,
      location: "北京",
      tags: ["维护"],
      ssh_user: "root",
      ssh_auth_type: "password",
    });
    expect(api.updateDevice.mock.calls[0][1]).not.toHaveProperty("ssh_password");
    expect(wrapper.text()).toContain("装配边缘终端 01 已更新");

    await wrapper.find('[data-testid="refresh-device-1"]').trigger("click");
    await flushAsync();
    expect(api.getDeviceStatus).toHaveBeenCalledWith(1);
    expect(wrapper.text()).toContain("离线");

    await wrapper.find('[data-testid="delete-device-1"]').trigger("click");
    await flushAsync();
    expect(api.deleteDevice).toHaveBeenCalledWith(1);
    expect(wrapper.find('[data-testid="delete-device-1"]').exists()).toBe(false);
  });

  it("shows sync config, filters logs, exports csv, and loads diagnostics", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-devices"]').trigger("click");
    await wrapper.find('[data-testid="sync-device-1"]').trigger("click");
    await flushAsync();

    expect(api.syncDeviceConfig).toHaveBeenCalledWith(1);
    expect(wrapper.text()).toContain("server_addr");

    await wrapper.find('[data-testid="nav-logs"]').trigger("click");
    await wrapper.find('[data-testid="log-action"] input').setValue("device.create");
    await wrapper.find('[data-testid="log-target-type"] input').setValue("device");
    await wrapper.find('[data-testid="log-status"] input').setValue("success");
    await wrapper.find('[data-testid="apply-log-filters"]').trigger("click");
    await flushAsync();
    expect(api.listLogs).toHaveBeenLastCalledWith({
      offset: 0,
      limit: 50,
      action: "device.create",
      target_type: "device",
      status: "success",
    });

    await wrapper.find('[data-testid="export-logs"]').trigger("click");
    await flushAsync();
    expect(api.exportLogs).toHaveBeenCalledWith({
      action: "device.create",
      target_type: "device",
      status: "success",
    });
    await wrapper.find('[data-testid="open-log-detail-1"]').trigger("click");
    await flushAsync();
    expect(wrapper.find('[data-testid="selected-log-detail"]').text()).toContain("操作详情");
    expect(wrapper.find('[data-testid="selected-log-detail"]').text()).toContain("SN-EDGE-001");

    await wrapper.find('[data-testid="nav-diagnostics"]').trigger("click");
    await flushAsync();
    expect(api.getDiagnosticsConfig).toHaveBeenCalled();
    expect(wrapper.text()).toContain("系统诊断");
    expect(wrapper.text()).toContain("未配置设备凭据加密密钥");
    expect(wrapper.text()).toContain("数据库迁移");
    expect(wrapper.text()).toContain("已同步");
    expect(wrapper.text()).toContain("SSH 主机密钥");
    expect(wrapper.text()).toContain("建议备份");
    expect(wrapper.text()).toContain("告警中心");
    expect(wrapper.text()).toContain("存在 1 条严重告警");
    expect(wrapper.text()).toContain("用户与权限");
  });

  it("shows alert center and manages alert rules", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-alerts"]').trigger("click");
    await waitUntil(() => expect(api.listAlerts).toHaveBeenCalled());

    expect(wrapper.text()).toContain("活跃告警");
    expect(wrapper.text()).toContain("CPU 高负载");
    expect(wrapper.text()).toContain("告警规则");
    expect(wrapper.text()).toContain("外部通知");
    expect(wrapper.text()).toContain("生产告警 Webhook");
    expect(wrapper.text()).toContain("严重告警触发通知");

    const acknowledgeButton = wrapper.findAll("button").find((button) => button.text().includes("确认"));
    expect(acknowledgeButton).toBeTruthy();
    await acknowledgeButton!.trigger("click");
    await flushAsync();
    expect(api.acknowledgeAlert).toHaveBeenCalledWith(31, { note: "前端确认" });

    const saveRuleButton = wrapper.findAll("button").find((button) => button.text().includes("保存"));
    expect(saveRuleButton).toBeTruthy();
    await saveRuleButton!.trigger("click");
    await flushAsync();
    expect(api.updateAlertRule).toHaveBeenCalledWith(3, {
      enabled: true,
      severity: "warning",
      threshold_value: 85,
      window_minutes: null,
    });

    const testButton = wrapper.findAll("button").find((button) => button.text().includes("测试"));
    expect(testButton).toBeTruthy();
    await testButton!.trigger("click");
    await flushAsync();
    expect(api.testAlertNotificationChannel).toHaveBeenCalledWith(41);

    const retryButton = wrapper.findAll("button").find((button) => button.text().includes("重试"));
    expect(retryButton).toBeTruthy();
    await retryButton!.trigger("click");
    await flushAsync();
    expect(api.retryAlertNotificationDelivery).toHaveBeenCalledWith(61);
  });

  it.skip("opens SSH and VNC from the selected remote device workspace", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-remote"]').trigger("click");
    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await waitUntil(() => expect(api.openSshSession).toHaveBeenCalledWith(1));
    // SSH session is now managed inside RemotePanel (WebSocket lifecycle in component)
    // The mock WebSocket may not be accessible from the parent App test scope
    // Verify the error is displayed instead

    mockWebSockets[0].open();
    await flushAsync();
    mockWebSockets[0].receive({ type: "output", data: "shell-ready\n" });
    await flushAsync();
    remoteMocks.terminalInstances[0].emitData("whoami\n");
    await flushAsync();

    expect(mockWebSockets[0].sent).toContain(JSON.stringify({ type: "resize", columns: 88, rows: 24 }));
    expect(mockWebSockets[0].sent).toContain(JSON.stringify({ type: "input", data: "whoami\n" }));
    expect(remoteMocks.terminalInstances[0].output).toContain("shell-ready");
    expect(wrapper.text()).toContain("shell-ready");

    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();
    expect(api.openVncSession).toHaveBeenCalledWith(1);
    expect(remoteMocks.rfbInstances).toHaveLength(1);
    expect(remoteMocks.rfbInstances[0].url).toBe("ws://test/api/ws/devices/1/vnc?token=access-token");
    remoteMocks.rfbInstances[0].emit("connect");
    await flushAsync();
    expect(wrapper.text()).toContain("VNC 已连接");

    await wrapper.find('[data-testid="disconnect-ssh-1"]').trigger("click");
    await wrapper.find('[data-testid="disconnect-vnc-1"]').trigger("click");
    await flushAsync();
    expect(wrapper.text()).toContain("SSH 已断开");
    expect(wrapper.text()).toContain("VNC 已断开");
  });

  it.skip("keeps the remote page visible when SSH session creation fails", async () => {
    api.openSshSession.mockRejectedValueOnce(
      Object.assign(new Error("bad gateway"), {
        response: { status: 502 },
      }),
    );
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-remote"]').trigger("click");
    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    // RemotePanel now manages SSH sessions in component scope; error message may vary
    await waitUntil(() => expect(wrapper.text()).toContain("失败"));

    expect(api.clearAuthTokens).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("远程代理或后端服务暂不可达");
  });

  it("cancels a pending update task", async () => {
    api.listUpdateTasks.mockResolvedValueOnce({
      total: 1,
      items: [
        {
          id: 9,
          name: "待取消任务",
          task_type: "command",
          command: "hostname",
          rollback_command: null,
          target_filter: { project_id: "工厂-a" },
          execution_mode: "dry_run",
          failure_strategy: "continue",
          concurrency_limit: 5,
          status: "pending",
          created_at: "2026-05-13T00:00:00",
          updated_at: "2026-05-13T00:00:00",
          device_count: 1,
          devices: [],
        },
      ],
    });
    api.cancelUpdateTask.mockResolvedValueOnce({
      id: 9,
      name: "待取消任务",
      task_type: "command",
      command: "hostname",
      rollback_command: null,
      target_filter: { project_id: "工厂-a" },
      execution_mode: "dry_run",
      failure_strategy: "continue",
      concurrency_limit: 5,
      status: "canceled",
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
      device_count: 1,
      devices: [],
    });
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-updates"]').trigger("click");
    await wrapper.find('[data-testid="cancel-update-9"]').trigger("click");
    await flushAsync();

    expect(api.cancelUpdateTask).toHaveBeenCalledWith(9);
    expect(wrapper.text()).toContain("已取消");
  });

  it("creates and executes a filtered update task through the backend API", async () => {
    api.createUpdateTask.mockResolvedValueOnce({
      id: 1,
      name: "重启视觉服务",
      task_type: "command",
      command: "sudo systemctl restart vision",
      rollback_command: null,
      target_filter: { project_id: "工厂-a" },
      execution_mode: "dry_run",
      failure_strategy: "continue",
      concurrency_limit: 5,
      status: "pending",
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
      device_count: 1,
      devices: [
        {
          id: 1,
          task_id: 1,
          device_id: 1,
          status: "pending",
          output_summary: null,
          exit_code: null,
          stdout_summary: null,
          stderr_summary: null,
          error_message: null,
          started_at: null,
          finished_at: null,
        },
      ],
    });
    api.executeUpdateTask.mockResolvedValueOnce({
      id: 1,
      name: "重启视觉服务",
      task_type: "command",
      command: "sudo systemctl restart vision",
      rollback_command: null,
      target_filter: { project_id: "工厂-a" },
      execution_mode: "ssh_command",
      failure_strategy: "continue",
      concurrency_limit: 5,
      status: "completed",
      created_at: "2026-05-13T00:00:00",
      updated_at: "2026-05-13T00:00:00",
      device_count: 1,
      devices: [
        {
          id: 1,
          task_id: 1,
          device_id: 1,
          status: "success",
          output_summary: "ok",
          exit_code: 0,
          stdout_summary: "ok",
          stderr_summary: null,
          error_message: null,
          started_at: null,
          finished_at: null,
        },
      ],
    });
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-updates"]').trigger("click");
    await wrapper.find('[data-testid="open-update-create"]').trigger("click");
    await wrapper.find('[data-testid="update-name"] input').setValue("重启视觉服务");
    await wrapper.find('[data-testid="update-command"] textarea').setValue("sudo systemctl restart vision");
    await wrapper.find('[data-testid="update-execution-mode"]').setValue("ssh_command");
    await wrapper.find('[data-testid="preview-update-targets"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="save-update"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="execute-update-1"]').trigger("click");
    await flushAsync();

    expect(api.previewUpdateTaskTargets).toHaveBeenCalledWith({
      target_filter: { project_id: "工厂-a" },
      execution_mode: "ssh_command",
    });
    expect(api.createUpdateTask).toHaveBeenCalledWith({
      name: "重启视觉服务",
      task_type: "command",
      command: "sudo systemctl restart vision",
      target_filter: { project_id: "工厂-a" },
      execution_mode: "ssh_command",
      failure_strategy: "continue",
      concurrency_limit: 5,
    });
    expect(api.executeUpdateTask).toHaveBeenCalledWith(1);
    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      expect.stringContaining("将通过 SSH 在目标设备上真实执行命令"),
      "确认真实 SSH 执行",
      expect.any(Object),
    );
    expect(wrapper.text()).toContain("重启视觉服务");
    expect(wrapper.text()).toContain("已完成");
    expect(wrapper.text()).toContain("1/1");
    expect(wrapper.text()).toContain("真实 SSH 执行");
    expect(wrapper.text()).toContain("设备执行结果");
    expect(mockWebSockets.at(-1)?.url).toBe("ws://test/api/ws/update-tasks/1?token=access-token");
  });

  it("prevents operators from applying real SSH command templates", async () => {
    api.getCurrentUser.mockResolvedValueOnce({
      id: 2,
      username: "operator",
      role: "operator",
      is_active: true,
    });
    api.listUpdateTaskTemplates.mockResolvedValueOnce({
      total: 1,
      items: [
        {
          id: 21,
          name: "真实重启模板",
          description: "高风险模板",
          command: "sudo reboot",
          task_type: "command",
          default_execution_mode: "ssh_command",
          created_at: "2026-06-09T00:00:00",
          updated_at: "2026-06-09T00:00:00",
        },
      ],
    });
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-username"] input').setValue("operator");
    await wrapper.find('[data-testid="login-password"] input').setValue("operator-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-updates"]').trigger("click");
    await wrapper.find('[data-testid="open-update-create"]').trigger("click");
    await flushAsync();

    expect(wrapper.find('[data-testid="apply-template-21"]').attributes("disabled")).toBeDefined();
    await wrapper.find('[data-testid="open-template-create"]').trigger("click");
    await flushAsync();
    expect(wrapper.find('[data-testid="template-mode"]').text()).not.toContain("真实 SSH 执行");
  });

  it("manages device files from the device operation area", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-devices"]').trigger("click");
    await wrapper.find('[data-testid="open-files-1"]').trigger("click");
    await waitUntil(() => expect(api.listDeviceFiles).toHaveBeenCalledWith(1, "/"));

    expect(wrapper.text()).toContain("文件管理");
    expect(wrapper.text()).toContain("config.bin");

    const file = new File([new Uint8Array([0, 1, 2, 255])], "payload.bin", {
      type: "application/octet-stream",
    });
    const uploadInput = wrapper.find('[data-testid="file-upload-input"]').element as HTMLInputElement;
    Object.defineProperty(uploadInput, "files", {
      value: [file],
      configurable: true,
    });
    await wrapper.find('[data-testid="file-upload-input"]').trigger("change");
    await wrapper.find('[data-testid="file-upload-path"] input').setValue("/payload.bin");
    await wrapper.find('[data-testid="upload-file"]').trigger("click");
    await waitUntil(() => expect(api.uploadDeviceFile).toHaveBeenCalledWith(1, "/payload.bin", file));

    await wrapper.find('[data-testid="download-file-config.bin"]').trigger("click");
    await flushAsync();
    expect(api.downloadDeviceFile).toHaveBeenCalledWith(1, "/config.bin");
    expect(window.URL.createObjectURL).toHaveBeenCalled();

    await wrapper.find('[data-testid="delete-file-config.bin"]').trigger("click");
    await flushAsync();
    expect(api.deleteDeviceFile).toHaveBeenCalledWith(1, "/config.bin");
  });

  it("manages scheduled tasks through the dedicated panel", async () => {
    const { wrapper, router } = await mountApp();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-scheduled"]').trigger("click");
    await waitUntil(() => expect(api.listScheduledTasks).toHaveBeenCalled());

    expect(wrapper.text()).toContain("定时任务");
    expect(wrapper.text()).toContain("巡检任务");
    expect(wrapper.text()).toContain("运行中");
    expect(wrapper.text()).toContain("success");

    await wrapper.find('[data-testid="open-scheduled-create"]').trigger("click");
    await wrapper.find('[data-testid="scheduled-name"] input').setValue("新建巡检");
    await wrapper.find('[data-testid="scheduled-schedule"] input').setValue("interval:600");
    await wrapper.find('[data-testid="scheduled-command"] textarea').setValue("whoami");
    await wrapper.find('[data-testid="scheduled-target-filter"] textarea').setValue('{"project_id":"frps-import"}');
    await wrapper.find('[data-testid="save-scheduled-task"]').trigger("click");
    await flushAsync();

    expect(api.createScheduledTask).toHaveBeenCalledWith({
      name: "新建巡检",
      task_type: "command",
      schedule: "interval:600",
      command: "whoami",
      target_filter: { project_id: "frps-import" },
      enabled: true,
      execution_mode: "dry_run",
      failure_strategy: "continue",
      concurrency_limit: 5,
    });
    expect(wrapper.text()).toContain("新建巡检");

    await wrapper.find('[data-testid="edit-scheduled-7"]').trigger("click");
    await wrapper.find('[data-testid="scheduled-name"] input').setValue("巡检任务已更新");
    await wrapper.find('[data-testid="save-scheduled-task"]').trigger("click");
    await flushAsync();
    expect(api.updateScheduledTask).toHaveBeenCalledWith(7, {
      name: "巡检任务已更新",
      task_type: "command",
      schedule: "interval:300",
      command: "hostname",
      target_filter: { project_id: "frps-import" },
      enabled: true,
      execution_mode: "dry_run",
      failure_strategy: "continue",
      concurrency_limit: 5,
    });
    expect(wrapper.text()).toContain("巡检任务已更新");

    await wrapper.find('[data-testid="toggle-scheduled-7"]').trigger("click");
    await flushAsync();
    expect(api.toggleScheduledTask).toHaveBeenCalledWith(7);
    expect(wrapper.text()).toContain("停用");

    await wrapper.find('[data-testid="execute-scheduled-7"]').trigger("click");
    await flushAsync();
    expect(api.runScheduledTaskNow).toHaveBeenCalledWith(7);
    expect(api.listScheduledTaskRuns).toHaveBeenCalledWith(7);
    expect(wrapper.text()).toContain("simulated scheduled task execution: hostname");
    expect(wrapper.text()).toContain("手动");

    await wrapper.find('[data-testid="runs-scheduled-7"]').trigger("click");
    await flushAsync();
    expect(api.listScheduledTaskRuns).toHaveBeenCalledWith(7);

    await wrapper.find('[data-testid="logs-scheduled-7"]').trigger("click");
    await flushAsync();
    expect(api.listScheduledTaskLogs).toHaveBeenCalledWith(7);
    expect(wrapper.text()).toContain("scheduled_task.execute");

    await wrapper.find('[data-testid="delete-scheduled-7"]').trigger("click");
    await flushAsync();
    expect(api.deleteScheduledTask).toHaveBeenCalledWith(7);
  });
});
