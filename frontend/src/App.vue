<script setup lang="ts">
import {
  Cpu,
  Document,
  Finished,
  Monitor,
  Operation,
  Plus,
  Refresh,
  Search,
  SwitchButton,
  VideoPlay,
  WarningFilled,
} from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, onMounted, reactive, ref } from "vue";

import {
  cancelUpdateTask,
  clearAuthTokens,
  buildApiWebSocketUrl,
  createDevice,
  createUpdateTask,
  deleteDevice,
  executeUpdateTask,
  getAccessToken,
  getDeviceStatus,
  getMonitoringOverview,
  hasStoredAccessToken,
  importFrpsDevices,
  listDevices,
  listGroups,
  listLogs,
  listUpdateTasks,
  loginAdmin,
  openSshSession,
  openVncSession,
  setAuthTokens,
  updateDevice,
  type DeviceCreateRequest,
  type DeviceRead,
  type DeviceUpdateRequest,
  type FrpsDiscoveredDevice,
  type FrpsImportRequest,
  type GroupRead,
  type MonitoringOverviewResponse,
  type OperationLogRead,
  type UpdateTaskCreateRequest,
  type UpdateTaskDeviceRead,
  type UpdateTaskRead,
} from "./api/platform";

type SectionId = "dashboard" | "devices" | "groups" | "remote" | "updates" | "logs";
type DeviceStatus = "online" | "offline" | "degraded" | "unknown";
type UpdateStatus = "pending" | "running" | "completed" | "canceled" | "partial_failed";
type ExecutionMode = "dry_run" | "ssh_command";

interface Device {
  id: number;
  name: string;
  device_sn: string;
  project_id: string;
  group: string;
  group_id: number | null;
  location: string;
  tags: string[];
  status: DeviceStatus;
  ssh_port: number | null;
  vnc_port: number | null;
  ssh_user: string;
  ssh_auth_type: string;
  ssh_credential_configured: boolean;
  cpu: number;
  memory: number;
}

interface Group {
  id: number;
  name: string;
  description: string;
  deviceCount: number;
}

interface UpdateTask {
  id: number;
  name: string;
  command: string;
  project_id: string;
  execution_mode: ExecutionMode;
  status: UpdateStatus;
  matched: number;
  completed: number;
  lastEvent: string;
  devices: UpdateTaskDeviceRead[];
}

interface AuditLog {
  id: number;
  action: string;
  target: string;
  status: string;
  detail: string;
  created_at: string;
}

type RemoteSessionStatus = "idle" | "connecting" | "ready" | "connected" | "failed" | "disconnected";

interface RemoteSessionUi {
  status: RemoteSessionStatus;
  message: string;
  websocketUrl: string;
  output: string;
}

const navItems: Array<{ id: SectionId; label: string; icon: unknown }> = [
  { id: "dashboard", label: "仪表盘", icon: Monitor },
  { id: "devices", label: "设备管理", icon: Cpu },
  { id: "groups", label: "分组管理", icon: Operation },
  { id: "remote", label: "远程连接", icon: VideoPlay },
  { id: "updates", label: "批量更新", icon: Finished },
  { id: "logs", label: "操作日志", icon: Document },
];

const authenticated = ref(hasStoredAccessToken());
const activeSection = ref<SectionId>("dashboard");
const loginPassword = ref("");
const loginError = ref("");
const deviceSearch = ref("");
const deviceCreateOpen = ref(false);
const deviceEditId = ref<number | null>(null);
const frpsImportOpen = ref(false);
const frpsImporting = ref(false);
const frpsImportResult = ref("");
const updateCreateOpen = ref(false);
const loading = ref(false);
const operationError = ref("");

const deviceForm = reactive({
  name: "",
  device_sn: "",
  project_id: "",
  group: "",
  location: "",
  tags: "",
  ssh_user: "ztl",
  ssh_auth_type: "password",
  ssh_password: "",
});

const updateForm = reactive({
  name: "",
  command: "",
  project_id: "",
  execution_mode: "dry_run" as ExecutionMode,
});

const frpsForm = reactive({
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

const devices = ref<Device[]>([]);
const groups = ref<Group[]>([]);
const updateTasks = ref<UpdateTask[]>([]);
const auditLogs = ref<AuditLog[]>([]);
const frpsImportItems = ref<FrpsDiscoveredDevice[]>([]);
const serverOverview = ref<MonitoringOverviewResponse | null>(null);
const remoteSessions = reactive<Record<string, RemoteSessionUi>>({});
const sshSockets = new Map<number, WebSocket>();

const statusType: Record<DeviceStatus, "success" | "warning" | "danger" | "info"> = {
  online: "success",
  offline: "danger",
  degraded: "warning",
  unknown: "info",
};

const deviceStatusText: Record<DeviceStatus, string> = {
  online: "在线",
  offline: "离线",
  degraded: "异常",
  unknown: "未知",
};

const updateStatusText: Record<UpdateStatus, string> = {
  pending: "待执行",
  running: "执行中",
  completed: "已完成",
  canceled: "已取消",
  partial_failed: "部分失败",
};

const logStatusText: Record<string, string> = {
  success: "成功",
  completed: "已完成",
  blocked: "已阻止",
  generated: "已生成",
  ready: "就绪",
};

const executionModeText: Record<ExecutionMode, string> = {
  dry_run: "演练模式",
  ssh_command: "真实 SSH 执行",
};

const taskDeviceStatusText: Record<string, string> = {
  pending: "等待执行",
  running: "执行中",
  success: "成功",
  failed: "失败",
  skipped: "已跳过",
  canceled: "已取消",
  completed: "已完成",
};

const visibleDevices = computed(() => {
  const keyword = deviceSearch.value.trim().toLowerCase();
  if (!keyword) {
    return devices.value;
  }
  return devices.value.filter((device) =>
    [device.name, device.device_sn, device.project_id, device.group, device.tags.join(",")]
      .join(" ")
      .toLowerCase()
      .includes(keyword),
  );
});

const deviceFormTitle = computed(() => (deviceEditId.value === null ? "创建设备" : "编辑设备"));

const overview = computed(() => {
  if (serverOverview.value) {
    return {
      devices: serverOverview.value.total_devices,
      online: serverOverview.value.online_devices,
      degraded: serverOverview.value.offline_devices + serverOverview.value.unknown_devices,
      updates: updateTasks.value.filter((task) => task.status === "completed").length,
    };
  }
  const online = devices.value.filter((device) => device.status === "online").length;
  const degraded = devices.value.filter((device) => device.status !== "online").length;
  return {
    devices: devices.value.length,
    online,
    degraded,
    updates: updateTasks.value.filter((task) => task.status === "completed").length,
  };
});

function normalizeDeviceStatus(status: string): DeviceStatus {
  if (status === "online" || status === "offline" || status === "degraded") {
    return status;
  }
  return "unknown";
}

function normalizeUpdateStatus(status: string): UpdateStatus {
  if (["pending", "running", "completed", "canceled", "partial_failed"].includes(status)) {
    return status as UpdateStatus;
  }
  return "pending";
}

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function groupNameFor(groupId: number | null, sourceGroups = groups.value): string {
  if (groupId === null) {
    return "未分组";
  }
  return sourceGroups.find((group) => group.id === groupId)?.name ?? `分组 ${groupId}`;
}

function formatTime(value: string | null): string {
  if (!value) {
    return "";
  }
  return value.replace("T", " ").slice(0, 16);
}

function mapDevice(device: DeviceRead, sourceGroups = groups.value): Device {
  return {
    id: device.id,
    name: device.name,
    device_sn: device.device_sn,
    project_id: device.project_id,
    group: groupNameFor(device.group_id, sourceGroups),
    group_id: device.group_id,
    location: device.location || "未分配",
    tags: device.tags ?? [],
    status: normalizeDeviceStatus(device.status),
    ssh_port: device.ssh_port,
    vnc_port: device.vnc_port,
    ssh_user: device.ssh_user,
    ssh_auth_type: device.ssh_auth_type,
    ssh_credential_configured: device.ssh_credential_configured,
    cpu: 0,
    memory: 0,
  };
}

function mapGroup(group: GroupRead, sourceDevices = devices.value): Group {
  return {
    id: group.id,
    name: group.name,
    description: group.description || "暂无描述",
    deviceCount: sourceDevices.filter((device) => device.group_id === group.id).length,
  };
}

function mapUpdateTask(task: UpdateTaskRead): UpdateTask {
  const completed = task.devices.filter((device) => ["success", "completed", "failed", "skipped"].includes(device.status)).length;
  const targetFilter = task.target_filter ?? {};
  const projectId = typeof targetFilter.project_id === "string" ? targetFilter.project_id : "全部项目";
  const lastDevice = task.devices.at(-1);
  return {
    id: task.id,
    name: task.name,
    command: task.command,
    project_id: projectId,
    execution_mode: task.execution_mode,
    status: normalizeUpdateStatus(task.status),
    matched: task.device_count,
    completed,
    lastEvent:
      lastDevice?.error_message ||
      lastDevice?.stdout_summary ||
      lastDevice?.stderr_summary ||
      lastDevice?.output_summary ||
      statusTextForTask(task.status),
    devices: task.devices,
  };
}

function mapLog(log: OperationLogRead): AuditLog {
  const target = log.target_type && log.target_id !== null ? `${log.target_type}:${log.target_id}` : log.target_type || "-";
  return {
    id: log.id,
    action: log.action,
    target,
    status: log.status,
    detail: log.detail || "",
    created_at: formatTime(log.created_at),
  };
}

function statusTextForTask(status: string): string {
  return updateStatusText[normalizeUpdateStatus(status)] ?? status;
}

function recalculateGroupCounts() {
  groups.value = groups.value.map((group) => ({
    ...group,
    deviceCount: devices.value.filter((device) => device.group_id === group.id).length,
  }));
}

function prependLocalLog(action: string, target: string, status: string, detail: string) {
  auditLogs.value.unshift({
    id: Date.now(),
    action,
    target,
    status,
    detail,
    created_at: new Date().toLocaleString("sv-SE").slice(0, 16),
  });
}

function remoteSessionKey(deviceId: number, sessionType: "ssh" | "vnc"): string {
  return `${sessionType}:${deviceId}`;
}

function remoteSessionFor(deviceId: number, sessionType: "ssh" | "vnc"): RemoteSessionUi {
  const key = remoteSessionKey(deviceId, sessionType);
  if (!remoteSessions[key]) {
    remoteSessions[key] = { status: "idle", message: "未连接", websocketUrl: "", output: "" };
  }
  return remoteSessions[key];
}

function setRemoteSession(deviceId: number, sessionType: "ssh" | "vnc", update: Partial<RemoteSessionUi>) {
  Object.assign(remoteSessionFor(deviceId, sessionType), update);
}

async function startSshSession(device: Device) {
  setRemoteSession(device.id, "ssh", { status: "connecting", message: "正在建立 SSH 会话", output: "" });
  try {
    const session = await openSshSession(device.id);
    const token = getAccessToken();
    const websocketUrl = session.websocket_url && token ? buildApiWebSocketUrl(session.websocket_url, token) : "";
    setRemoteSession(device.id, "ssh", {
      status: "ready",
      message: `SSH 会话已就绪，远程端口 ${session.remote_port}`,
      websocketUrl,
    });
    if (!websocketUrl || typeof WebSocket === "undefined") {
      return;
    }
    sshSockets.get(device.id)?.close();
    const socket = new WebSocket(websocketUrl);
    sshSockets.set(device.id, socket);
    socket.onopen = () => {
      setRemoteSession(device.id, "ssh", { status: "connected", message: "SSH 已连接" });
      socket.send(JSON.stringify({ type: "resize", columns: 120, rows: 32 }));
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(String(event.data)) as { type: string; data?: string; status?: string; message?: string };
        if (message.type === "output") {
          const current = remoteSessionFor(device.id, "ssh");
          current.output += message.data ?? "";
        } else if (message.type === "status") {
          setRemoteSession(device.id, "ssh", { status: "connected", message: `SSH ${message.status ?? "已连接"}` });
        } else if (message.type === "error") {
          setRemoteSession(device.id, "ssh", { status: "failed", message: message.message ?? "SSH 连接失败" });
        }
      } catch {
        const current = remoteSessionFor(device.id, "ssh");
        current.output += String(event.data);
      }
    };
    socket.onerror = () => setRemoteSession(device.id, "ssh", { status: "failed", message: "SSH WebSocket 连接失败" });
    socket.onclose = () => {
      if (remoteSessionFor(device.id, "ssh").status !== "failed") {
        setRemoteSession(device.id, "ssh", { status: "disconnected", message: "SSH 已断开" });
      }
      sshSockets.delete(device.id);
    };
  } catch (error) {
    setRemoteSession(device.id, "ssh", { status: "failed", message: "无法创建 SSH 会话" });
  }
}

async function startVncSession(device: Device) {
  setRemoteSession(device.id, "vnc", { status: "connecting", message: "正在准备 VNC 代理", output: "" });
  try {
    const session = await openVncSession(device.id);
    const token = getAccessToken();
    const websocketUrl = session.websocket_url && token ? buildApiWebSocketUrl(session.websocket_url, token) : "";
    setRemoteSession(device.id, "vnc", {
      status: "ready",
      message: `VNC 代理已就绪，远程端口 ${session.remote_port}`,
      websocketUrl,
    });
  } catch (error) {
    setRemoteSession(device.id, "vnc", { status: "failed", message: "无法创建 VNC 会话" });
  }
}

function disconnectSshSession(deviceId: number) {
  const socket = sshSockets.get(deviceId);
  if (socket && typeof WebSocket !== "undefined" && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "close" }));
  }
  socket?.close();
  sshSockets.delete(deviceId);
  setRemoteSession(deviceId, "ssh", { status: "disconnected", message: "SSH 已断开" });
}

function isAuthFailure(error: unknown): boolean {
  const status = (error as { response?: { status?: number } }).response?.status;
  return status === 401 || status === 403;
}

function isGatewayFailure(error: unknown): boolean {
  const status = (error as { response?: { status?: number } }).response?.status;
  return status === 502 || status === 503 || status === 504;
}

async function loadPlatformData() {
  loading.value = true;
  operationError.value = "";
  try {
    const [groupResponse, deviceResponse, logResponse, updateResponse, overviewResponse] = await Promise.all([
      listGroups(),
      listDevices(),
      listLogs(),
      listUpdateTasks(),
      getMonitoringOverview(),
    ]);
    const mappedGroups = groupResponse.items.map((group) => mapGroup(group, []));
    devices.value = deviceResponse.items.map((device) => mapDevice(device, mappedGroups));
    groups.value = groupResponse.items.map((group) => mapGroup(group, devices.value));
    auditLogs.value = logResponse.items.map(mapLog);
    updateTasks.value = updateResponse.items.map(mapUpdateTask);
    serverOverview.value = overviewResponse;
  } catch (error) {
    if (isAuthFailure(error)) {
      operationError.value = "登录状态已过期，请重新登录。";
      clearAuthTokens();
      authenticated.value = false;
      return;
    }
    operationError.value = isGatewayFailure(error) ? "后端服务不可达或代理配置错误，请检查 Nginx /api 反向代理和后端进程。" : "无法从后端加载平台数据，请确认后端服务已启动。";
  } finally {
    loading.value = false;
  }
}

async function refreshLogsAndOverview() {
  const [logResponse, overviewResponse] = await Promise.all([listLogs(), getMonitoringOverview()]);
  auditLogs.value = logResponse.items.map(mapLog);
  serverOverview.value = overviewResponse;
}

async function login() {
  if (!loginPassword.value) {
    loginError.value = "请输入管理员密码";
    return;
  }
  loading.value = true;
  loginError.value = "";
  try {
    const token = await loginAdmin("admin", loginPassword.value);
    setAuthTokens(token.access_token, token.refresh_token);
    authenticated.value = true;
    loginPassword.value = "";
    await loadPlatformData();
  } catch (error) {
    clearAuthTokens();
    authenticated.value = false;
    loginError.value = "密码与本地管理员账户不匹配";
  } finally {
    loading.value = false;
  }
}

function logout() {
  authenticated.value = false;
  clearAuthTokens();
  loginPassword.value = "";
  devices.value = [];
  groups.value = [];
  updateTasks.value = [];
  auditLogs.value = [];
  serverOverview.value = null;
}

function openDeviceCreate() {
  deviceEditId.value = null;
  Object.assign(deviceForm, {
    name: "",
    device_sn: "",
    project_id: "",
    group: groups.value[0]?.name ?? "",
    location: "",
    tags: "",
    ssh_user: "ztl",
    ssh_auth_type: "password",
    ssh_password: "",
  });
  deviceCreateOpen.value = true;
}

function openDeviceEdit(device: Device) {
  deviceEditId.value = device.id;
  Object.assign(deviceForm, {
    name: device.name,
    device_sn: device.device_sn,
    project_id: device.project_id,
    group: device.group,
    location: device.location === "未分配" ? "" : device.location,
    tags: device.tags.join(","),
    ssh_user: device.ssh_user,
    ssh_auth_type: device.ssh_auth_type,
    ssh_password: "",
  });
  deviceCreateOpen.value = true;
}

async function saveDevice() {
  if (!deviceForm.name || !deviceForm.device_sn || !deviceForm.project_id) {
    prependLocalLog("设备校验", deviceEditId.value === null ? "新设备" : `设备：${deviceEditId.value}`, "blocked", "设备名称、序列号和项目号为必填项");
    return;
  }
  const basePayload = {
    name: deviceForm.name,
    project_id: deviceForm.project_id,
    location: deviceForm.location || undefined,
    tags: parseTags(deviceForm.tags),
    ssh_user: deviceForm.ssh_user || "ztl",
    ssh_auth_type: deviceForm.ssh_auth_type || "password",
  };
  const passwordPayload = deviceForm.ssh_password ? { ssh_password: deviceForm.ssh_password } : {};
  try {
    if (deviceEditId.value === null) {
      const payload: DeviceCreateRequest = {
        ...basePayload,
        ...passwordPayload,
        device_sn: deviceForm.device_sn,
      };
      const created = await createDevice(payload);
      devices.value.push(mapDevice(created));
    } else {
      const payload: DeviceUpdateRequest = {
        ...basePayload,
        ...passwordPayload,
      };
      const updated = await updateDevice(deviceEditId.value, payload);
      const index = devices.value.findIndex((device) => device.id === updated.id);
      if (index >= 0) {
        devices.value[index] = mapDevice(updated);
      }
    }
    recalculateGroupCounts();
    await refreshLogsAndOverview();
    deviceCreateOpen.value = false;
  } catch (error) {
    prependLocalLog(deviceEditId.value === null ? "创建设备" : "编辑设备", "设备", "blocked", "保存设备失败，请检查后端返回。");
  }
}

async function removeDevice(device: Device) {
  try {
    await ElMessageBox.confirm(`确定删除设备 ${device.name}（${device.device_sn}）？`, "删除设备", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await deleteDevice(device.id);
    devices.value = devices.value.filter((item) => item.id !== device.id);
    recalculateGroupCounts();
    await refreshLogsAndOverview();
  } catch (error) {
    prependLocalLog("删除设备", `设备：${device.id}`, "blocked", "删除设备失败，请检查后端返回。");
  }
}

async function refreshDeviceStatus(device: Device) {
  try {
    const status = await getDeviceStatus(device.id);
    const index = devices.value.findIndex((item) => item.id === device.id);
    if (index >= 0) {
      devices.value[index] = {
        ...devices.value[index],
        status: normalizeDeviceStatus(status.status),
      };
    }
  } catch (error) {
    prependLocalLog("刷新设备状态", `设备：${device.id}`, "blocked", "刷新状态失败，请检查后端返回。");
  }
}

async function importFromFrps() {
  frpsImporting.value = true;
  frpsImportResult.value = "";
  frpsImportItems.value = [];
  const payload: FrpsImportRequest = {
    dashboard_url: frpsForm.dashboard_url,
    username: frpsForm.username,
    password: frpsForm.password,
    ssh_port_start: Number(frpsForm.ssh_port_start),
    ssh_port_end: Number(frpsForm.ssh_port_end),
    vnc_port_start: Number(frpsForm.vnc_port_start),
    vnc_port_end: Number(frpsForm.vnc_port_end),
    project_id: frpsForm.project_id,
    location: frpsForm.location || "frps",
    overwrite_project_location: frpsForm.overwrite_project_location,
  };
  try {
    const result = await importFrpsDevices(payload);
    frpsImportItems.value = result.items;
    frpsImportResult.value = `发现 ${result.total} 台，新增 ${result.created} 台，同步 ${result.synced} 台，跳过 ${result.skipped} 台，冲突 ${result.conflicts} 台`;
    await loadPlatformData();
  } catch (error) {
    frpsImportResult.value = "frps 导入失败，请检查 Dashboard 地址、账号密码和后端网络";
  } finally {
    frpsImporting.value = false;
  }
}

function openUpdateCreate() {
  Object.assign(updateForm, {
    name: "",
    command: "hostname",
    project_id: devices.value[0]?.project_id ?? "",
    execution_mode: "dry_run" as ExecutionMode,
  });
  updateCreateOpen.value = true;
}

async function saveUpdate() {
  if (!updateForm.name || !updateForm.command) {
    prependLocalLog("更新任务校验", "新任务", "blocked", "任务名称和命令为必填项");
    return;
  }
  const payload: UpdateTaskCreateRequest = {
    name: updateForm.name,
    task_type: "command",
    command: updateForm.command,
    target_filter: updateForm.project_id ? { project_id: updateForm.project_id } : {},
    execution_mode: updateForm.execution_mode,
    failure_strategy: "continue",
    concurrency_limit: 5,
  };
  if (payload.execution_mode === "ssh_command") {
    const confirmed = await confirmRealSshTask(updateForm.command, updateForm.project_id || "全部项目");
    if (!confirmed) {
      return;
    }
  }
  try {
    const created = await createUpdateTask(payload);
    updateTasks.value.push(mapUpdateTask(created));
    await refreshLogsAndOverview();
    updateCreateOpen.value = false;
  } catch (error) {
    prependLocalLog("创建更新任务", "新任务", "blocked", "创建更新任务失败，请检查后端返回。");
  }
}

async function executeUpdate(task: UpdateTask) {
  if (task.execution_mode === "ssh_command") {
    const confirmed = await confirmRealSshTask(task.command, task.project_id);
    if (!confirmed) {
      return;
    }
  }
  task.status = "running";
  task.lastEvent = "正在请求后端执行";
  try {
    const executed = await executeUpdateTask(task.id);
    const mapped = mapUpdateTask(executed);
    const index = updateTasks.value.findIndex((item) => item.id === task.id);
    if (index >= 0) {
      updateTasks.value[index] = mapped;
    }
    await refreshLogsAndOverview();
  } catch (error) {
    task.status = "partial_failed";
    task.lastEvent = "后端执行失败";
    prependLocalLog("执行更新任务", `更新任务：${task.id}`, "blocked", "执行失败，请检查后端任务状态。");
  }
}

async function cancelUpdate(task: UpdateTask) {
  try {
    await ElMessageBox.confirm(`确定取消更新任务 ${task.name}？`, "取消更新任务", {
      type: "warning",
      confirmButtonText: "取消任务",
      cancelButtonText: "返回",
    });
  } catch {
    return;
  }
  try {
    const canceled = await cancelUpdateTask(task.id);
    const mapped = mapUpdateTask(canceled);
    const index = updateTasks.value.findIndex((item) => item.id === task.id);
    if (index >= 0) {
      updateTasks.value[index] = mapped;
    }
    await refreshLogsAndOverview();
  } catch (error) {
    prependLocalLog("取消更新任务", `更新任务：${task.id}`, "blocked", "取消任务失败，请检查后端任务状态。");
  }
}

async function confirmRealSshTask(command: string, target: string): Promise<boolean> {
  try {
    await ElMessageBox.confirm(
      `将通过 SSH 在目标设备上真实执行命令。\n目标：${target}\n命令：${command}\n建议先使用演练模式确认范围。`,
      "确认真实 SSH 执行",
      {
        type: "warning",
        confirmButtonText: "确认执行",
        cancelButtonText: "取消",
      },
    );
    return true;
  } catch {
    return false;
  }
}

function selectSection(section: SectionId) {
  activeSection.value = section;
}

onMounted(() => {
  if (authenticated.value) {
    void loadPlatformData();
  }
});
</script>

<template>
  <section v-if="!authenticated" class="login-page">
    <div class="login-panel">
      <div>
        <p class="eyebrow">远程管理</p>
        <h1>边缘设备管理平台</h1>
        <p class="login-copy">登录后可管理设备、远程访问、批量更新、监控指标和操作日志。</p>
      </div>
      <el-form class="login-form" @submit.prevent="login">
        <el-form-item>
          <div data-testid="login-password" class="input-wrap">
            <el-input
              v-model="loginPassword"
              type="password"
              show-password
              placeholder="管理员密码"
              @keyup.enter="login"
            />
          </div>
        </el-form-item>
        <p v-if="loginError" class="form-error">{{ loginError }}</p>
        <el-button data-testid="login-submit" type="primary" class="login-button" :loading="loading" @click="login">
          登录
        </el-button>
      </el-form>
    </div>
  </section>

  <el-container v-else class="app-shell">
    <el-aside class="sidebar" width="232px">
      <div class="brand">
        <span class="brand-mark">EP</span>
        <span>边缘设备管理平台</span>
      </div>
      <el-menu :default-active="activeSection" class="nav">
        <el-menu-item
          v-for="item in navItems"
          :key="item.id"
          :index="item.id"
          :data-testid="`nav-${item.id}`"
          @click="selectSection(item.id)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <p class="eyebrow">设备运维</p>
          <h2>{{ navItems.find((item) => item.id === activeSection)?.label }}</h2>
        </div>
        <div class="topbar-actions">
          <el-tag type="success" effect="light">真实 API</el-tag>
          <el-button :icon="SwitchButton" circle title="退出登录" @click="logout" />
        </div>
      </el-header>

      <el-main class="content">
        <el-alert
          v-if="operationError"
          class="validation-alert"
          type="warning"
          :icon="WarningFilled"
          show-icon
          :closable="false"
          :title="operationError"
        />

        <section v-if="activeSection === 'dashboard'" class="page-section">
          <div class="stat-grid">
            <div class="stat-tile">
              <span>设备总数</span>
              <strong>{{ overview.devices }}</strong>
            </div>
            <div class="stat-tile success">
              <span>在线</span>
              <strong>{{ overview.online }}</strong>
            </div>
            <div class="stat-tile warning">
              <span>异常/未知</span>
              <strong>{{ overview.degraded }}</strong>
            </div>
            <div class="stat-tile info">
              <span>已完成更新</span>
              <strong>{{ overview.updates }}</strong>
            </div>
          </div>

          <div class="two-column">
            <section class="panel">
              <div class="panel-header">
                <h3>资源快照</h3>
                <el-button :icon="Refresh" text :loading="loading" @click="loadPlatformData">刷新</el-button>
              </div>
              <div v-for="device in devices" :key="device.id" class="metric-row">
                <div>
                  <strong>{{ device.name }}</strong>
                  <span>{{ device.project_id }}</span>
                </div>
                <el-progress :percentage="device.cpu" :stroke-width="10" />
                <el-progress :percentage="device.memory" :stroke-width="10" color="#4f46e5" />
              </div>
            </section>

            <section class="panel">
              <div class="panel-header">
                <h3>最近审计</h3>
                <el-button text @click="selectSection('logs')">查看全部</el-button>
              </div>
              <div v-for="log in auditLogs.slice(0, 5)" :key="log.id" class="log-row">
                <el-tag size="small" :type="log.status === 'success' || log.status === 'completed' ? 'success' : 'warning'">
                  {{ logStatusText[log.status] ?? log.status }}
                </el-tag>
                <span>{{ log.action }}</span>
                <small>{{ log.detail }}</small>
              </div>
            </section>
          </div>
        </section>

        <section v-if="activeSection === 'devices'" class="page-section">
          <div class="toolbar">
            <el-input v-model="deviceSearch" :prefix-icon="Search" placeholder="按名称、序列号、项目、分组或标签搜索" />
            <el-button data-testid="open-device-create" type="primary" :icon="Plus" @click="openDeviceCreate">
              新建设备
            </el-button>
            <el-button data-testid="open-frps-import" :icon="Refresh" @click="frpsImportOpen = !frpsImportOpen">
              导入 frps
            </el-button>
          </div>

          <section v-if="frpsImportOpen" class="form-panel" aria-label="导入 frps 设备">
            <div class="panel-header">
              <h3>导入 frps 已有设备</h3>
              <el-button text @click="frpsImportOpen = false">关闭</el-button>
            </div>
            <div class="form-grid">
              <div data-testid="frps-url" class="input-wrap"><el-input v-model="frpsForm.dashboard_url" placeholder="Dashboard 地址" /></div>
              <div data-testid="frps-username" class="input-wrap"><el-input v-model="frpsForm.username" placeholder="用户名" /></div>
              <div data-testid="frps-password" class="input-wrap"><el-input v-model="frpsForm.password" type="password" show-password placeholder="密码" /></div>
              <div data-testid="frps-project" class="input-wrap"><el-input v-model="frpsForm.project_id" placeholder="导入项目号" /></div>
              <div data-testid="frps-location" class="input-wrap"><el-input v-model="frpsForm.location" placeholder="部署位置" /></div>
              <el-checkbox data-testid="frps-overwrite" v-model="frpsForm.overwrite_project_location">覆盖项目号和位置</el-checkbox>
              <el-input-number v-model="frpsForm.ssh_port_start" :min="1" controls-position="right" />
              <el-input-number v-model="frpsForm.ssh_port_end" :min="1" controls-position="right" />
              <el-input-number v-model="frpsForm.vnc_port_start" :min="1" controls-position="right" />
              <el-input-number v-model="frpsForm.vnc_port_end" :min="1" controls-position="right" />
            </div>
            <p v-if="frpsImportResult" class="muted">{{ frpsImportResult }}</p>
            <el-table v-if="frpsImportItems.length" :data="frpsImportItems" size="small" row-key="device_sn" empty-text="暂无导入结果">
              <el-table-column prop="device_sn" label="设备 SN" min-width="130" />
              <el-table-column prop="ssh_port" label="SSH" width="90" />
              <el-table-column prop="vnc_port" label="VNC" width="90" />
              <el-table-column prop="import_status" label="结果" width="120" />
              <el-table-column prop="detail" label="详情" min-width="180" />
            </el-table>
            <div class="form-actions">
              <el-button data-testid="import-frps" type="primary" :loading="frpsImporting" @click="importFromFrps">开始导入</el-button>
            </div>
          </section>

          <div class="table-panel">
            <el-table :data="visibleDevices" row-key="id" empty-text="暂无设备">
              <el-table-column prop="name" label="设备" min-width="180" />
              <el-table-column prop="device_sn" label="序列号" min-width="150" />
              <el-table-column prop="project_id" label="项目" width="130" />
              <el-table-column prop="group" label="分组" width="110" />
              <el-table-column label="标签" min-width="150">
                <template #default="{ row }">
                  <el-tag v-for="tag in row.tags" :key="tag" size="small" class="tag-chip">{{ tag }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="statusType[row.status as DeviceStatus]">{{ deviceStatusText[row.status as DeviceStatus] }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="远程" width="150">
                <template #default="{ row }">
                  <el-button size="small" :icon="Monitor" @click="selectSection('remote')">SSH</el-button>
                  <el-button size="small" :icon="VideoPlay" @click="selectSection('remote')">VNC</el-button>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="230">
                <template #default="{ row }">
                  <el-button :data-testid="`edit-device-${row.id}`" size="small" @click="openDeviceEdit(row)">编辑</el-button>
                  <el-button :data-testid="`refresh-device-${row.id}`" size="small" :icon="Refresh" @click="refreshDeviceStatus(row)">刷新</el-button>
                  <el-button :data-testid="`delete-device-${row.id}`" size="small" type="danger" @click="removeDevice(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <section v-if="deviceCreateOpen" class="form-panel" :aria-label="deviceFormTitle">
            <div class="panel-header">
              <h3>{{ deviceFormTitle }}</h3>
              <el-button text @click="deviceCreateOpen = false">关闭</el-button>
            </div>
            <div class="form-grid">
              <div data-testid="device-name" class="input-wrap"><el-input v-model="deviceForm.name" placeholder="设备名称" /></div>
              <div data-testid="device-sn" class="input-wrap"><el-input v-model="deviceForm.device_sn" :disabled="deviceEditId !== null" placeholder="设备序列号" /></div>
              <div data-testid="device-project" class="input-wrap"><el-input v-model="deviceForm.project_id" placeholder="项目号" /></div>
              <el-input v-model="deviceForm.group" placeholder="分组（当前仅用于显示）" />
              <el-input v-model="deviceForm.location" placeholder="位置" />
              <div data-testid="device-tags" class="input-wrap"><el-input v-model="deviceForm.tags" placeholder="标签，用逗号分隔" /></div>
              <div data-testid="device-ssh-user" class="input-wrap"><el-input v-model="deviceForm.ssh_user" placeholder="SSH 用户" /></div>
              <div data-testid="device-ssh-auth-type" class="input-wrap"><el-input v-model="deviceForm.ssh_auth_type" placeholder="凭据类型" /></div>
              <div data-testid="device-ssh-password" class="input-wrap"><el-input v-model="deviceForm.ssh_password" type="password" show-password placeholder="SSH 密码" /></div>
            </div>
            <p class="muted">SSH 密码不会从接口回显；编辑设备时留空表示不修改已有凭据。</p>
            <div class="form-actions">
              <el-button data-testid="save-device" type="primary" :loading="loading" @click="saveDevice">保存设备</el-button>
            </div>
          </section>
        </section>

        <section v-if="activeSection === 'groups'" class="page-section">
          <div class="list-grid">
            <div v-for="group in groups" :key="group.id" class="item-card">
              <h3>{{ group.name }}</h3>
              <p>{{ group.description }}</p>
              <el-tag>{{ group.deviceCount }} 台设备</el-tag>
            </div>
          </div>
        </section>

        <section v-if="activeSection === 'remote'" class="page-section">
          <div class="list-grid">
            <div v-for="device in devices" :key="device.id" class="remote-card">
              <div>
                <h3>{{ device.name }}</h3>
                <p>{{ device.device_sn }} · {{ device.location }}</p>
              </div>
              <div class="remote-actions">
                <el-button
                  :data-testid="`open-ssh-${device.id}`"
                  type="primary"
                  :icon="Monitor"
                  :loading="remoteSessionFor(device.id, 'ssh').status === 'connecting'"
                  @click="startSshSession(device)"
                >
                  SSH :{{ device.ssh_port ?? "-" }}
                </el-button>
                <el-button
                  :data-testid="`open-vnc-${device.id}`"
                  :icon="VideoPlay"
                  :loading="remoteSessionFor(device.id, 'vnc').status === 'connecting'"
                  @click="startVncSession(device)"
                >
                  VNC :{{ device.vnc_port ?? "-" }}
                </el-button>
                <el-button
                  v-if="remoteSessionFor(device.id, 'ssh').status === 'connected'"
                  :data-testid="`disconnect-ssh-${device.id}`"
                  text
                  @click="disconnectSshSession(device.id)"
                >
                  断开
                </el-button>
              </div>
              <div class="remote-session-state">
                <el-tag size="small">{{ remoteSessionFor(device.id, "ssh").message }}</el-tag>
                <el-tag size="small" type="info">{{ remoteSessionFor(device.id, "vnc").message }}</el-tag>
              </div>
              <pre v-if="remoteSessionFor(device.id, 'ssh').output" class="terminal-output">{{
                remoteSessionFor(device.id, "ssh").output
              }}</pre>
              <p v-if="remoteSessionFor(device.id, 'vnc').websocketUrl" class="muted">
                VNC WebSocket：{{ remoteSessionFor(device.id, "vnc").websocketUrl }}
              </p>
            </div>
          </div>
        </section>

        <section v-if="activeSection === 'updates'" class="page-section">
          <div class="toolbar">
            <div>
              <h3>更新任务</h3>
              <p class="muted">创建按条件筛选的任务，并跟踪每台设备的执行进度。</p>
            </div>
            <el-button data-testid="open-update-create" type="primary" :icon="Plus" @click="openUpdateCreate">
              新建更新
            </el-button>
          </div>

          <section v-if="updateCreateOpen" class="form-panel" aria-label="创建更新任务">
            <div class="panel-header">
              <h3>创建更新任务</h3>
              <el-button text @click="updateCreateOpen = false">关闭</el-button>
            </div>
            <div class="form-grid">
              <div data-testid="update-name" class="input-wrap"><el-input v-model="updateForm.name" placeholder="任务名称" /></div>
              <div data-testid="update-project" class="input-wrap"><el-input v-model="updateForm.project_id" placeholder="目标项目" /></div>
              <label class="field-label">
                <span>执行模式</span>
                <select data-testid="update-execution-mode" v-model="updateForm.execution_mode" class="native-select">
                  <option value="dry_run">演练模式</option>
                  <option value="ssh_command">真实 SSH 执行</option>
                </select>
              </label>
              <div data-testid="update-command" class="input-wrap textarea-wrap">
                <el-input v-model="updateForm.command" type="textarea" :rows="3" placeholder="命令或脚本" />
              </div>
            </div>
            <p v-if="updateForm.execution_mode === 'ssh_command'" class="muted">
              真实 SSH 执行会连接目标设备。建议先使用 hostname、whoami、uptime 等只读命令验收。
            </p>
            <div class="form-actions">
              <el-button data-testid="save-update" type="primary" @click="saveUpdate">保存更新任务</el-button>
            </div>
          </section>

          <div class="table-panel">
            <el-table :data="updateTasks" row-key="id" empty-text="暂无更新任务">
              <el-table-column prop="name" label="任务" min-width="190" />
              <el-table-column prop="project_id" label="目标" width="130" />
              <el-table-column label="模式" width="130">
                <template #default="{ row }">{{ executionModeText[row.execution_mode as ExecutionMode] }}</template>
              </el-table-column>
              <el-table-column label="进度" width="140">
                <template #default="{ row }">{{ row.completed }}/{{ row.matched }}</template>
              </el-table-column>
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'completed' ? 'success' : 'info'">{{ updateStatusText[row.status as UpdateStatus] }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="lastEvent" label="最新事件" min-width="190" />
              <el-table-column label="设备结果" min-width="260">
                <template #default="{ row }">
                  <div v-for="device in row.devices" :key="device.id" class="task-device-result">
                    <el-tag size="small" :type="device.status === 'success' ? 'success' : device.status === 'failed' ? 'danger' : 'info'">
                      {{ taskDeviceStatusText[device.status] ?? device.status }}
                    </el-tag>
                    <span>设备 {{ device.device_id }}</span>
                    <small v-if="device.exit_code !== null">退出码 {{ device.exit_code }}</small>
                    <small v-if="device.stdout_summary">{{ device.stdout_summary }}</small>
                    <small v-if="device.stderr_summary">{{ device.stderr_summary }}</small>
                    <small v-if="device.error_message">{{ device.error_message }}</small>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="190">
                <template #default="{ row }">
                  <el-button
                    :data-testid="`execute-update-${row.id}`"
                    size="small"
                    type="primary"
                    :disabled="row.status === 'completed'"
                    @click="executeUpdate(row)"
                  >
                    执行
                  </el-button>
                  <el-button
                    v-if="row.status === 'pending' || row.status === 'running'"
                    :data-testid="`cancel-update-${row.id}`"
                    size="small"
                    type="warning"
                    @click="cancelUpdate(row)"
                  >
                    取消
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </section>

        <section v-if="activeSection === 'logs'" class="page-section">
          <div class="toolbar">
            <h3>操作日志</h3>
            <el-button :icon="Document">导出 CSV</el-button>
          </div>
          <div class="table-panel">
            <el-table :data="auditLogs" row-key="id" empty-text="暂无日志">
              <el-table-column prop="created_at" label="时间" width="160" />
              <el-table-column prop="action" label="操作" min-width="150" />
              <el-table-column prop="target" label="目标" min-width="130" />
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'blocked' ? 'warning' : 'success'">{{ logStatusText[row.status] ?? row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="detail" label="详情" min-width="220" />
            </el-table>
          </div>
        </section>
      </el-main>
    </el-container>
  </el-container>
</template>
