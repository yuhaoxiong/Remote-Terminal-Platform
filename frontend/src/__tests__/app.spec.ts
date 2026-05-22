import { mount } from "@vue/test-utils";
import ElementPlus, { ElMessageBox } from "element-plus";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import App from "../App.vue";
import * as platformApi from "../api/platform";

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
  getAccessToken: vi.fn(() => "access-token"),
  getDeviceStatus: vi.fn(),
  getDiagnosticsConfig: vi.fn(),
  hasStoredAccessToken: vi.fn(() => false),
  importFrpsDevices: vi.fn(),
  listDevices: vi.fn(),
  listDeviceMetrics: vi.fn(),
  listGroups: vi.fn(),
  listLogs: vi.fn(),
  listUpdateTasks: vi.fn(),
  previewUpdateTaskTargets: vi.fn(),
  listUpdateTaskTemplates: vi.fn(),
  createUpdateTaskTemplate: vi.fn(),
  updateUpdateTaskTemplate: vi.fn(),
  deleteUpdateTaskTemplate: vi.fn(),
  loginAdmin: vi.fn(),
  openSshSession: vi.fn(),
  openVncSession: vi.fn(),
  setAuthTokens: vi.fn(),
  syncDeviceConfig: vi.fn(),
  updateDevice: vi.fn(),
  updateGroup: vi.fn(),
  getMonitoringOverview: vi.fn(),
}));

const api = vi.mocked(platformApi);

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
  api.loginAdmin.mockResolvedValue({
    access_token: "access-token",
    refresh_token: "refresh-token",
    token_type: "bearer",
  });
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
  });
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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

    expect(wrapper.text()).toContain("边缘设备管理平台");
    expect(wrapper.text()).toContain("登录");

    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    expect(wrapper.text()).toContain("请输入管理员密码");
    expect(wrapper.findAll(".form-error")).toHaveLength(1);
    expect(api.loginAdmin).not.toHaveBeenCalled();

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.loginAdmin).toHaveBeenCalledWith("admin", "admin-pass");
    expect(api.setAuthTokens).toHaveBeenCalledWith("access-token", "refresh-token");
    expect(api.listDevices).toHaveBeenCalled();
    expect(api.listGroups).toHaveBeenCalled();
    expect(api.listLogs).toHaveBeenCalled();
    expect(api.listUpdateTasks).toHaveBeenCalled();
    expect(api.getMonitoringOverview).toHaveBeenCalled();
    expect(wrapper.text()).toContain("设备运维");
    expect(wrapper.text()).toContain("批量更新");
  });

  it("shows one validation message for an incorrect password", async () => {
    api.loginAdmin.mockRejectedValueOnce(new Error("bad credentials"));
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

    await wrapper.find('[data-testid="login-password"] input').setValue("wrong-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(wrapper.text()).toContain("密码与本地管理员账户不匹配");
    expect(wrapper.findAll(".form-error")).toHaveLength(1);
  });

  it("keeps the authenticated surface visible when a data endpoint fails after login", async () => {
    api.listUpdateTasks.mockRejectedValueOnce(
      Object.assign(new Error("server error"), {
        response: { status: 500 },
      }),
    );
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();

    expect(api.clearAuthTokens).not.toHaveBeenCalled();
    expect(wrapper.find('[data-testid="login-submit"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("指标加载失败");
    expect(wrapper.text()).not.toContain("CPU 0%");
  });

  it("changes the admin password and returns to the login page", async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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

    await wrapper.find('[data-testid="nav-diagnostics"]').trigger("click");
    await flushAsync();
    expect(api.getDiagnosticsConfig).toHaveBeenCalled();
    expect(wrapper.text()).toContain("系统诊断");
    expect(wrapper.text()).toContain("未配置设备凭据加密密钥");
    expect(wrapper.text()).toContain("数据库迁移");
    expect(wrapper.text()).toContain("已同步");
    expect(wrapper.text()).toContain("SSH 主机密钥");
    expect(wrapper.text()).toContain("建议备份");
  });

  it("opens SSH and VNC from the selected remote device workspace", async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-remote"]').trigger("click");
    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await waitUntil(() => expect(api.openSshSession).toHaveBeenCalledWith(1));
    expect(mockWebSockets).toHaveLength(1);
    expect(mockWebSockets[0].url).toBe("ws://test/api/ws/devices/1/ssh?token=access-token");

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

  it("keeps the remote page visible when SSH session creation fails", async () => {
    api.openSshSession.mockRejectedValueOnce(
      Object.assign(new Error("bad gateway"), {
        response: { status: 502 },
      }),
    );
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

    await wrapper.find('[data-testid="login-password"] input').setValue("admin-pass");
    await wrapper.find('[data-testid="login-submit"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="nav-remote"]').trigger("click");
    await wrapper.find('[data-testid="select-remote-device-1"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await waitUntil(() => expect(wrapper.text()).toContain("远程代理或后端服务暂不可达"));

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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

  it("manages device files from the device operation area", async () => {
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
    const wrapper = mount(App, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          teleport: true,
        },
      },
    });

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
