import { mount } from "@vue/test-utils";
import ElementPlus, { ElMessageBox } from "element-plus";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";

import App from "../App.vue";
import * as platformApi from "../api/platform";

vi.mock("../api/platform", () => ({
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
  getAccessToken: vi.fn(() => "access-token"),
  getDeviceStatus: vi.fn(),
  getDiagnosticsConfig: vi.fn(),
  hasStoredAccessToken: vi.fn(() => false),
  importFrpsDevices: vi.fn(),
  listDevices: vi.fn(),
  listGroups: vi.fn(),
  listLogs: vi.fn(),
  listUpdateTasks: vi.fn(),
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
  api.changePassword.mockResolvedValue(undefined);
  api.exportLogs.mockResolvedValue(new Blob(["id,action\n1,device.create\n"], { type: "text/csv" }));
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
  await nextTick();
  await Promise.resolve();
  await nextTick();
}

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
    vi.stubGlobal("WebSocket", undefined);
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
  });

  it("opens real remote session descriptors from the remote page", async () => {
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
    await wrapper.find('[data-testid="open-ssh-1"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="open-vnc-1"]').trigger("click");
    await flushAsync();

    expect(api.openSshSession).toHaveBeenCalledWith(1);
    expect(api.openVncSession).toHaveBeenCalledWith(1);
    expect(wrapper.text()).toContain("SSH");
    expect(wrapper.text()).toContain("VNC");
    expect(wrapper.text()).toContain("10000");
    expect(wrapper.text()).toContain("10500");
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
    await wrapper.find('[data-testid="update-project"] input').setValue("工厂-a");
    await wrapper.find('[data-testid="update-execution-mode"]').setValue("ssh_command");
    await wrapper.find('[data-testid="save-update"]').trigger("click");
    await flushAsync();
    await wrapper.find('[data-testid="execute-update-1"]').trigger("click");
    await flushAsync();

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
    expect(wrapper.text()).toContain("退出码 0");
  });
});
