<script setup lang="ts">
import {
  Cpu,
  Document,
  Finished,
  FolderOpened,
  Monitor,
  Operation,
  Plus,
  Refresh,
  Search,
  Setting,
  UserFilled,
  VideoPlay,
  WarningFilled,
} from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import {
  AUTH_EXPIRED_EVENT,
  buildApiWebSocketUrl,
  changePassword,
  clearAuthTokens,
  getAlertSummary,
  getAccessToken,
  getCurrentUser,
  getDiagnosticsConfig,
  getMonitoringOverview,

  listDevices,
  listDeviceMetrics,
  listGroups,
  listUpdateTasks,
  loginAdmin,
  openSshSession,
  openVncSession,
  setAuthTokens,
  type AlertSummaryResponse,
  type CurrentUserResponse,
  type DiagnosticsConfigResponse,
  type DeviceMetricRead,
  type ListLogsParams,
  type MonitoringOverviewResponse,
  type UpdateTaskRead,
} from "./api/platform";
import { fetchHealth } from "./api/health";
import { useAuthStore } from "./stores/auth";
import { useDevicesStore, mapDevice, normalizeDeviceStatus, type Device, type DeviceStatus } from "./stores/devices";
import { useGroupsStore, mapGroup, groupNameFor } from "./stores/groups";
import { useLogsStore, type AuditLog } from "./stores/logs";
import {
  useUpdatesStore,
  mapUpdateTask,
  updateStatusText,
  executionModeText,
  type UpdateStatus,
  type ExecutionMode,
  type UpdateTask,
} from "./stores/updates";
import { formatTime } from "./utils/format";
import AlertCenterPanel from "./components/AlertCenterPanel.vue";
import AppSidebar from "./components/AppSidebar.vue";
import AppTopbar from "./components/AppTopbar.vue";
import FilesPanel from "./components/FilesPanel.vue";
import GroupsPanel from "./components/GroupsPanel.vue";
import DiagnosticsPanel from "./components/DiagnosticsPanel.vue";
import DashboardPanel from "./components/DashboardPanel.vue";
import DevicesPanel from "./components/DevicesPanel.vue";
import LayoutShell from "./components/LayoutShell.vue";
import LogsPanel from "./components/LogsPanel.vue";
import RemotePanel from "./components/RemotePanel.vue";
import ScheduledTaskPanel from "./components/ScheduledTaskPanel.vue";
import SystemSettingsPanel from "./components/SystemSettingsPanel.vue";
import UpdatesPanel from "./components/UpdatesPanel.vue";
import UserManagementPanel from "./components/UserManagementPanel.vue";

type SectionId = "dashboard" | "devices" | "groups" | "remote" | "files" | "updates" | "scheduled" | "alerts" | "users" | "logs" | "diagnostics" | "settings";
type RemoteSessionStatus = "idle" | "connecting" | "ready" | "connected" | "failed" | "disconnected";

interface RemoteSessionUi {
  status: RemoteSessionStatus;
  message: string;
  websocketUrl: string;
  output: string;
}

interface XtermTerminal {
  cols: number;
  rows: number;
  loadAddon(addon: unknown): void;
  open(element: HTMLElement): void;
  write(data: string): void;
  writeln(data: string): void;
  onData(callback: (data: string) => void): { dispose: () => void };
  dispose(): void;
}

interface XtermFitAddon {
  fit(): void;
  dispose?: () => void;
}

interface SshTerminalHandle {
  terminal: XtermTerminal;
  fitAddon: XtermFitAddon;
  dataDisposable: { dispose: () => void };
  resizeObserver: ResizeObserver | null;
}

interface VncClient {
  disconnect(): void;
  addEventListener(type: string, callback: (event: Event) => void): void;
}

const navItems: Array<{ id: SectionId; label: string; icon: Component; group: "overview" | "operations" | "governance"; adminOnly?: boolean }> = [
  { id: "dashboard", label: "仪表盘", icon: Monitor, group: "overview" },
  { id: "devices", label: "设备管理", icon: Cpu, group: "operations" },
  { id: "remote", label: "远程连接", icon: VideoPlay, group: "operations" },
  { id: "files", label: "文件管理", icon: FolderOpened, group: "operations" },
  { id: "updates", label: "批量更新", icon: Finished, group: "operations" },
  { id: "scheduled", label: "定时任务", icon: Operation, group: "operations" },
  { id: "alerts", label: "告警中心", icon: WarningFilled, group: "operations" },
  { id: "diagnostics", label: "系统诊断", icon: WarningFilled, group: "governance" },
  { id: "settings", label: "系统设置", icon: Setting, group: "governance", adminOnly: true },
  { id: "logs", label: "操作日志", icon: Document, group: "governance" },
  { id: "groups", label: "分组管理", icon: Operation, group: "governance" },
  { id: "users", label: "用户管理", icon: UserFilled, group: "governance", adminOnly: true },
];

const authStore = useAuthStore();
const { authenticated, currentUser, isAdmin } = storeToRefs(authStore);
const devicesStore = useDevicesStore();
const {
  devices,
  deviceSearch,
  selectedGroupId,
  deviceStatusFilter,
  deviceProjectFilter,
  deviceTagFilter,
  filePanelDevice,
  visibleDevices,
} = storeToRefs(devicesStore);
const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const { recalculateGroupCounts } = groupsStore;
const logsStore = useLogsStore();
const { auditLogs, auditLogsTotal } = storeToRefs(logsStore);
const { mapLog, prependLocalLog } = logsStore;
const updatesStore = useUpdatesStore();
const { updateTasks, pendingTaskCount } = storeToRefs(updatesStore);
const router = useRouter();
const route = useRoute();

const activeSection = computed<SectionId>(() => {
  const routeName = typeof route.name === "string" ? route.name : "";
  return navItems.some((item) => item.id === routeName) ? (routeName as SectionId) : "dashboard";
});

const loginUsername = ref("admin");
const loginPassword = ref("");
const loginError = ref("");
const passwordChangeOpen = ref(false);
const loading = ref(false);
const operationError = ref("");
const remoteDeviceSearch = ref("");
const selectedRemoteDeviceId = ref<number | null>(null);
const sshTerminalHostRef = ref<HTMLElement | null>(null);
const vncCanvasHostRef = ref<HTMLElement | null>(null);

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
});


const serverOverview = ref<MonitoringOverviewResponse | null>(null);
const alertSummary = ref<AlertSummaryResponse | null>(null);
const diagnosticsConfig = ref<DiagnosticsConfigResponse | null>(null);
const diagnosticsLoading = ref(false);
const backendHealthStatus = ref<"checking" | "healthy" | "failed">("checking");
const backendHealthDetail = ref("检测中");
const remoteSessions = reactive<Record<string, RemoteSessionUi>>({});
const sshSockets = new Map<number, WebSocket>();
const sshTerminals = new Map<number, SshTerminalHandle>();
const vncClients = new Map<number, VncClient>();

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

const logStatusText: Record<string, string> = {
  success: "成功",
  completed: "已完成",
  blocked: "已阻止",
  generated: "已生成",
  ready: "就绪",
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

const metricLoadWarning = ref("");

const visibleNavItems = computed(() => navItems.filter((item) => !item.adminOnly || isAdmin.value));
const activeSectionTitle = computed(() => {
  const routeLabel = route.meta.label;
  return typeof routeLabel === "string" ? routeLabel : navItems.find((item) => item.id === activeSection.value)?.label ?? "仪表盘";
});
const currentRoleLabel = computed(() => (isAdmin.value ? "管理员" : "运维人员"));
const schedulerRunning = computed(() => diagnosticsConfig.value?.scheduler.running ?? null);

const remoteVisibleDevices = computed(() => {
  const keyword = remoteDeviceSearch.value.trim().toLowerCase();
  return devices.value.filter((device) => {
    if (!keyword) {
      return true;
    }
    return [device.name, device.device_sn, device.project_id, device.location, device.group, String(device.ssh_port ?? ""), String(device.vnc_port ?? "")]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });
});

const selectedRemoteDevice = computed(() => devices.value.find((device) => device.id === selectedRemoteDeviceId.value) ?? null);
const selectedSshSession = computed(() =>
  selectedRemoteDevice.value ? remoteSessionFor(selectedRemoteDevice.value.id, "ssh") : null,
);
const selectedVncSession = computed(() =>
  selectedRemoteDevice.value ? remoteSessionFor(selectedRemoteDevice.value.id, "vnc") : null,
);



function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function withLatestMetric(device: Device, metric: DeviceMetricRead | undefined): Device {
  if (!metric) {
    return {
      ...device,
      cpu: null,
      memory: null,
      disk: null,
      metricRecordedAt: null,
      metricStale: false,
      metricLoadFailed: false,
    };
  }
  return {
    ...device,
    status: normalizeDeviceStatus(metric.status || device.status),
    cpu: metric.cpu_percent,
    memory: metric.memory_percent,
    disk: metric.disk_percent,
    metricRecordedAt: metric.recorded_at,
    metricStale: (() => {
      if (!metric.recorded_at) return false;
      const ts = new Date(metric.recorded_at).getTime();
      return !Number.isNaN(ts) && Date.now() - ts > 10 * 60 * 1000;
    })(),
    metricLoadFailed: false,
  };
}

async function attachLatestMetrics(sourceDevices: Device[]): Promise<Device[]> {
  let failedCount = 0;
  const enriched = await Promise.all(
    sourceDevices.map(async (device) => {
      try {
        const response = await listDeviceMetrics(device.id, 1);
        return withLatestMetric(device, response.items[0]);
      } catch (error) {
        if (isAuthFailure(error)) {
          throw error;
        }
        failedCount += 1;
        return { ...device, metricLoadFailed: true };
      }
    }),
  );
  metricLoadWarning.value = failedCount > 0 ? `有 ${failedCount} 台设备指标加载失败` : "";
  return enriched;
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

function openFilePanel(device: Device) {
  filePanelDevice.value = device;
  void selectSection("files");
}

function selectRemoteDevice(device: Device) {
  selectedRemoteDeviceId.value = device.id;
}

async function openSshFromDevice(device: Device) {
  selectRemoteDevice(device);
  await selectSection("remote");
  await nextTick();
  await startSshSession(device);
}

async function openVncFromDevice(device: Device) {
  selectRemoteDevice(device);
  await selectSection("remote");
  await nextTick();
  await startVncSession(device);
}

function remoteUnavailableReason(device: Device, sessionType: "ssh" | "vnc"): string {
  if (sessionType === "ssh") {
    if (device.ssh_port === null) {
      return "缺少 SSH 端口";
    }
    if (!device.ssh_credential_configured) {
      return "凭据未配置";
    }
  }
  if (sessionType === "vnc" && device.vnc_port === null) {
    return "缺少 VNC 端口";
  }
  return "";
}

function canOpenRemote(device: Device, sessionType: "ssh" | "vnc"): boolean {
  return remoteUnavailableReason(device, sessionType) === "";
}

function remoteErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (isGatewayFailure(error)) {
    return "远程代理或后端服务暂不可达";
  }
  return fallback;
}

function disposeSshTerminal(deviceId: number) {
  const handle = sshTerminals.get(deviceId);
  if (!handle) {
    return;
  }
  handle.resizeObserver?.disconnect();
  handle.dataDisposable.dispose();
  handle.fitAddon.dispose?.();
  handle.terminal.dispose();
  sshTerminals.delete(deviceId);
}

function fitAndReportSshSize(deviceId: number) {
  const handle = sshTerminals.get(deviceId);
  if (!handle) {
    return;
  }
  handle.fitAddon.fit();
  const socket = sshSockets.get(deviceId);
  if (socket && typeof WebSocket !== "undefined" && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "resize", columns: handle.terminal.cols || 120, rows: handle.terminal.rows || 32 }));
  }
}

async function prepareSshTerminal(deviceId: number): Promise<XtermTerminal | null> {
  await nextTick();
  const host = sshTerminalHostRef.value;
  if (!host) {
    return null;
  }
  disposeSshTerminal(deviceId);
  host.replaceChildren();
  const [{ Terminal }, { FitAddon }] = await Promise.all([import("@xterm/xterm"), import("@xterm/addon-fit")]);
  const terminal = new Terminal({
    cursorBlink: true,
    convertEol: true,
    fontFamily: "Consolas, 'Courier New', monospace",
    fontSize: 13,
    theme: {
      background: "#0f172a",
      foreground: "#d1fae5",
      cursor: "#38bdf8",
    },
  }) as XtermTerminal;
  const fitAddon = new FitAddon() as XtermFitAddon;
  terminal.loadAddon(fitAddon);
  terminal.open(host);
  const dataDisposable = terminal.onData((data) => {
    const socket = sshSockets.get(deviceId);
    if (socket && typeof WebSocket !== "undefined" && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: "input", data }));
    }
  });
  const resizeObserver =
    typeof ResizeObserver === "undefined"
      ? null
      : new ResizeObserver(() => {
          fitAndReportSshSize(deviceId);
        });
  resizeObserver?.observe(host);
  sshTerminals.set(deviceId, { terminal, fitAddon, dataDisposable, resizeObserver });
  fitAndReportSshSize(deviceId);
  return terminal;
}

async function startSshSession(device: Device) {
  if (!canOpenRemote(device, "ssh")) {
    setRemoteSession(device.id, "ssh", { status: "failed", message: remoteUnavailableReason(device, "ssh") });
    return;
  }
  selectRemoteDevice(device);
  setRemoteSession(device.id, "ssh", { status: "connecting", message: "正在建立 SSH 会话", output: "" });
  try {
    const terminal = await prepareSshTerminal(device.id);
    terminal?.writeln("正在建立 SSH 会话...");
    const session = await openSshSession(device.id);
    const token = getAccessToken();
    const websocketUrl = session.websocket_url && token ? buildApiWebSocketUrl(session.websocket_url, token) : "";
    setRemoteSession(device.id, "ssh", {
      status: "ready",
      message: `SSH 会话已就绪，远程端口 ${session.remote_port}`,
      websocketUrl,
    });
    if (!websocketUrl || typeof WebSocket === "undefined") {
      terminal?.writeln("浏览器环境不支持 WebSocket，无法打开 SSH 终端。");
      return;
    }
    sshSockets.get(device.id)?.close();
    const socket = new WebSocket(websocketUrl);
    sshSockets.set(device.id, socket);
    socket.onopen = () => {
      setRemoteSession(device.id, "ssh", { status: "connected", message: "SSH 已连接" });
      fitAndReportSshSize(device.id);
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(String(event.data)) as { type: string; data?: string; status?: string; message?: string };
        if (message.type === "output") {
          const current = remoteSessionFor(device.id, "ssh");
          current.output += message.data ?? "";
          sshTerminals.get(device.id)?.terminal.write(message.data ?? "");
        } else if (message.type === "status") {
          setRemoteSession(device.id, "ssh", { status: "connected", message: `SSH ${message.status ?? "已连接"}` });
        } else if (message.type === "error") {
          setRemoteSession(device.id, "ssh", { status: "failed", message: message.message ?? "SSH 连接失败" });
          sshTerminals.get(device.id)?.terminal.writeln(message.message ?? "SSH 连接失败");
        }
      } catch {
        const current = remoteSessionFor(device.id, "ssh");
        current.output += String(event.data);
        sshTerminals.get(device.id)?.terminal.write(String(event.data));
      }
    };
    socket.onerror = () => {
      setRemoteSession(device.id, "ssh", { status: "failed", message: "SSH WebSocket 连接失败" });
      sshTerminals.get(device.id)?.terminal.writeln("SSH WebSocket 连接失败");
    };
    socket.onclose = () => {
      if (remoteSessionFor(device.id, "ssh").status !== "failed") {
        setRemoteSession(device.id, "ssh", { status: "disconnected", message: "SSH 已断开" });
      }
      sshSockets.delete(device.id);
    };
  } catch (error) {
    const message = remoteErrorMessage(error, "无法创建 SSH 会话");
    setRemoteSession(device.id, "ssh", { status: "failed", message });
    sshTerminals.get(device.id)?.terminal.writeln(message);
  }
}

async function startVncSession(device: Device) {
  if (!canOpenRemote(device, "vnc")) {
    setRemoteSession(device.id, "vnc", { status: "failed", message: remoteUnavailableReason(device, "vnc") });
    return;
  }
  selectRemoteDevice(device);
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
    await nextTick();
    if (!websocketUrl || !vncCanvasHostRef.value) {
      setRemoteSession(device.id, "vnc", { status: "failed", message: "无法创建 VNC 画面容器" });
      return;
    }
    disconnectVncSession(device.id, false);
    const { default: RFB } = await import("@novnc/novnc");
    const client = new RFB(vncCanvasHostRef.value, websocketUrl, {}) as VncClient;
    client.addEventListener("connect", () => {
      setRemoteSession(device.id, "vnc", { status: "connected", message: "VNC 已连接" });
    });
    client.addEventListener("disconnect", () => {
      if (remoteSessionFor(device.id, "vnc").status !== "failed") {
        setRemoteSession(device.id, "vnc", { status: "disconnected", message: "VNC 已断开" });
      }
      vncClients.delete(device.id);
    });
    client.addEventListener("securityfailure", () => {
      setRemoteSession(device.id, "vnc", { status: "failed", message: "VNC 安全协商失败" });
    });
    vncClients.set(device.id, client);
  } catch (error) {
    setRemoteSession(device.id, "vnc", { status: "failed", message: remoteErrorMessage(error, "无法创建 VNC 会话") });
  }
}

function disconnectSshSession(deviceId: number) {
  const socket = sshSockets.get(deviceId);
  if (socket && typeof WebSocket !== "undefined" && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "close" }));
  }
  socket?.close();
  sshSockets.delete(deviceId);
  disposeSshTerminal(deviceId);
  setRemoteSession(deviceId, "ssh", { status: "disconnected", message: "SSH 已断开" });
}

function disconnectVncSession(deviceId: number, updateStatus = true) {
  const client = vncClients.get(deviceId);
  client?.disconnect();
  vncClients.delete(deviceId);
  if (updateStatus) {
    setRemoteSession(deviceId, "vnc", { status: "disconnected", message: "VNC 已断开" });
  }
}

async function requestVncFullscreen() {
  await nextTick();
  const target = vncCanvasHostRef.value;
  if (!target?.requestFullscreen) {
    if (selectedRemoteDevice.value) {
      setRemoteSession(selectedRemoteDevice.value.id, "vnc", { message: "当前浏览器不支持全屏" });
    }
    return;
  }
  await target.requestFullscreen();
}

function isAuthFailure(error: unknown): boolean {
  const status = (error as { response?: { status?: number } }).response?.status;
  return status === 401;
}

function isPermissionFailure(error: unknown): boolean {
  const status = (error as { response?: { status?: number } }).response?.status;
  return status === 403;
}

function isGatewayFailure(error: unknown): boolean {
  const status = (error as { response?: { status?: number } }).response?.status;
  return status === 502 || status === 503 || status === 504;
}

async function loadPlatformData() {
  loading.value = true;
  operationError.value = "";
  try {
    const [userResponse, groupResponse, deviceResponse, updateResponse, overviewResponse, alertSummaryResponse] = await Promise.all([
      getCurrentUser(),
      listGroups(),
      listDevices(),
      listUpdateTasks(),
      getMonitoringOverview(),
      getAlertSummary(),
    ]);
    currentUser.value = userResponse;
    const mappedGroups = groupResponse.items.map((group) => mapGroup(group, []));
    const mappedDevices = deviceResponse.items.map((device) => mapDevice(device, mappedGroups));
    devices.value = await attachLatestMetrics(mappedDevices);
    groups.value = groupResponse.items.map((group) => mapGroup(group, devices.value));
    updateTasks.value = updateResponse.items.map(mapUpdateTask);
    serverOverview.value = overviewResponse;
    alertSummary.value = alertSummaryResponse;
  } catch (error) {
    if (isAuthFailure(error)) {
      operationError.value = "登录状态已过期，请重新登录。";
      clearAuthTokens();
      authenticated.value = false;
      return;
    }
    if (isPermissionFailure(error)) {
      operationError.value = "当前账号无权限加载该数据，请联系管理员调整权限。";
      return;
    }
    operationError.value = isGatewayFailure(error) ? "后端服务不可达或代理配置错误，请检查 Nginx /api 反向代理和后端进程。" : "无法从后端加载平台数据，请确认后端服务已启动。";
  } finally {
    loading.value = false;
  }
}

async function refreshLogsAndOverview() {
  const [overviewResponse, alertSummaryResponse] = await Promise.all([
    getMonitoringOverview(),
    getAlertSummary(),
  ]);
  serverOverview.value = overviewResponse;
  alertSummary.value = alertSummaryResponse;
}

async function login() {
  if (!loginUsername.value.trim()) {
    loginError.value = "请输入用户名";
    return;
  }
  if (!loginPassword.value) {
    loginError.value = "请输入密码";
    return;
  }
  loading.value = true;
  loginError.value = "";
  try {
    const token = await loginAdmin(loginUsername.value.trim(), loginPassword.value);
    setAuthTokens(token.access_token, token.refresh_token);
    authenticated.value = true;
    loginPassword.value = "";
    await loadPlatformData();
  } catch (error) {
    clearAuthTokens();
    authenticated.value = false;
    loginError.value = "用户名或密码不正确";
  } finally {
    loading.value = false;
  }
}

function logout() {
  authenticated.value = false;
  clearAuthTokens();
  currentUser.value = null;
  loginPassword.value = "";
  devices.value = [];
  groups.value = [];
  updateTasks.value = [];
  auditLogs.value = [];
  auditLogsTotal.value = 0;
  serverOverview.value = null;
  alertSummary.value = null;
  diagnosticsConfig.value = null;
  metricLoadWarning.value = "";
}

function handleAuthExpired() {
  logout();
  operationError.value = "登录状态已过期，请重新登录。";
  loginError.value = "登录状态已过期，请重新登录。";
}

function openPasswordChange() {
  Object.assign(passwordForm, {
    old_password: "",
    new_password: "",
    confirm_password: "",
  });
  passwordChangeOpen.value = true;
}

async function savePasswordChange() {
  if (!passwordForm.old_password || !passwordForm.new_password) {
    prependLocalLog("修改密码校验", "管理员账户", "blocked", "原密码和新密码为必填项");
    return;
  }
  if (passwordForm.new_password.length < 8) {
    prependLocalLog("修改密码校验", "管理员账户", "blocked", "新密码至少 8 位");
    return;
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    prependLocalLog("修改密码校验", "管理员账户", "blocked", "两次输入的新密码不一致");
    return;
  }
  try {
    await changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    });
    prependLocalLog("修改密码", "管理员账户", "success", "密码已修改，请重新登录");
    passwordChangeOpen.value = false;
    logout();
  } catch (error) {
    prependLocalLog("修改密码", "管理员账户", "blocked", "修改失败，请检查原密码是否正确");
  }
}

function selectGroup(groupId: number | null) {
  selectedGroupId.value = groupId;
  void selectSection("devices");
}

function targetSummaryForFilter(targetFilter: Record<string, unknown>): string {
  const deviceIds = Array.isArray(targetFilter.device_ids) ? targetFilter.device_ids : [];
  if (deviceIds.length > 0) {
    return `手动选择 ${deviceIds.length} 台设备`;
  }
  const parts: string[] = [];
  if (typeof targetFilter.project_id === "string" && targetFilter.project_id) {
    parts.push(`项目 ${targetFilter.project_id}`);
  }
  if (typeof targetFilter.group_id === "number") {
    parts.push(`分组 ${groupNameFor(targetFilter.group_id)}`);
  }
  if (typeof targetFilter.status === "string" && targetFilter.status) {
    parts.push(`状态 ${deviceStatusText[normalizeDeviceStatus(targetFilter.status)]}`);
  }
  const tags = Array.isArray(targetFilter.tags) ? targetFilter.tags.filter((tag): tag is string => typeof tag === "string") : [];
  if (tags.length > 0) {
    parts.push(`标签 ${tags.join(", ")}`);
  }
  return parts.length > 0 ? parts.join("，") : "全部设备";
}

function targetSummaryForTask(task: UpdateTask): string {
  return `${targetSummaryForFilter(task.target_filter)}，匹配 ${task.matched} 台`;
}

async function loadDiagnosticsConfig() {
  diagnosticsLoading.value = true;
  try {
    diagnosticsConfig.value = await getDiagnosticsConfig();
  } catch (error) {
    prependLocalLog("加载诊断配置", "系统", "blocked", "无法读取诊断配置，请检查后端服务。");
  } finally {
    diagnosticsLoading.value = false;
  }
}

async function loadBackendHealth() {
  backendHealthStatus.value = "checking";
  backendHealthDetail.value = "检测中";
  try {
    const health = await fetchHealth();
    backendHealthStatus.value = health.status === "ok" ? "healthy" : "failed";
    backendHealthDetail.value = health.status === "ok" ? "正常" : health.status;
  } catch {
    backendHealthStatus.value = "failed";
    backendHealthDetail.value = "异常";
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

async function selectSection(section: SectionId) {
  if ((section === "users" || section === "settings") && !isAdmin.value) {
    operationError.value = section === "users" ? "当前账号无权限访问用户管理。" : "当前账号无权限访问系统设置。";
    return;
  }
  operationError.value = "";
  await router.push({ name: section });
}

watch([activeSection, authenticated], ([section, isAuthenticated]) => {
  if (section === "diagnostics" && isAuthenticated) {
    void loadDiagnosticsConfig();
  }
});

watch([authenticated, currentUser, activeSection], ([isAuthenticated, user, section]) => {
  const navItem = navItems.find((item) => item.id === section);
  if (isAuthenticated && user && navItem?.adminOnly && user.role !== "admin") {
    operationError.value = section === "users" ? "当前账号无权限访问用户管理。" : "当前账号无权限访问系统设置。";
    void router.replace({ name: "dashboard" });
  }
});

onMounted(() => {
  window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  void loadBackendHealth();
  if (authenticated.value) {
    void loadPlatformData();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  for (const deviceId of sshSockets.keys()) {
    disconnectSshSession(deviceId);
  }
  updatesStore.stopAllProgress();
  for (const deviceId of vncClients.keys()) {
    disconnectVncSession(deviceId, false);
  }
});
</script>

<template>
  <section v-if="!authenticated" class="login-page">
    <div class="login-hero">
      <div class="login-brand">
        <span class="brand-mark">EP</span>
        <div>
          <h1>AI 边缘设备管理平台</h1>
          <p>基于 Debian 的边缘设备远程运维</p>
        </div>
      </div>
      <div class="login-capabilities">
        <div>
          <strong>设备接入</strong>
          <span>frps 自动发现与统一纳管</span>
        </div>
        <div>
          <strong>远程运维</strong>
          <span>Web SSH、VNC 与文件管理</span>
        </div>
        <div>
          <strong>批量更新</strong>
          <span>演练、真实执行与进度追踪</span>
        </div>
        <div>
          <strong>告警闭环</strong>
          <span>规则、通知、确认与恢复</span>
        </div>
      </div>
      <div class="login-visual" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
    <div class="login-panel">
      <div>
        <p class="eyebrow">欢迎登录</p>
        <h2>边缘运维控制台</h2>
        <p class="login-copy">支持 JWT 登录、角色权限和会话审计。</p>
      </div>
      <el-form class="login-form" @submit.prevent="login">
        <label class="login-field">
          <span>用户名</span>
          <div data-testid="login-username" class="input-wrap">
            <el-input v-model="loginUsername" placeholder="请输入用户名" @keyup.enter="login" />
          </div>
        </label>
        <label class="login-field">
          <span>密码</span>
          <div data-testid="login-password" class="input-wrap">
            <el-input
              v-model="loginPassword"
              type="password"
              show-password
              placeholder="请输入密码"
              @keyup.enter="login"
            />
          </div>
        </label>
        <p v-if="loginError" class="form-error">{{ loginError }}</p>
        <el-button data-testid="login-submit" type="primary" class="login-button" :loading="loading" @click="login">
          登录
        </el-button>
      </el-form>
    </div>
  </section>

  <LayoutShell v-else>
    <template #sidebar>
      <AppSidebar :active="activeSection" :items="visibleNavItems" @select="(id) => void selectSection(id as SectionId)" />
    </template>
    <template #topbar>
      <AppTopbar
        :title="activeSectionTitle"
        :user-name="currentUser?.username"
        :role-label="currentRoleLabel"
        :api-healthy="backendHealthStatus === 'healthy'"
        :api-detail="backendHealthDetail"
        :scheduler-running="schedulerRunning"
        @refresh-health="loadBackendHealth"
        @change-password="openPasswordChange"
        @logout="logout"
      />
    </template>
        <el-alert
          v-if="operationError"
          class="validation-alert"
          type="warning"
          :icon="WarningFilled"
          show-icon
          :closable="false"
          :title="operationError"
        />

        <section v-if="passwordChangeOpen" class="form-panel" aria-label="修改管理员密码">
          <div class="panel-header">
            <h3>修改管理员密码</h3>
            <el-button text @click="passwordChangeOpen = false">关闭</el-button>
          </div>
          <div class="form-grid">
            <div data-testid="old-password" class="input-wrap">
              <el-input v-model="passwordForm.old_password" type="password" show-password placeholder="原密码" />
            </div>
            <div data-testid="new-password" class="input-wrap">
              <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="新密码，至少 8 位" />
            </div>
            <div data-testid="confirm-password" class="input-wrap">
              <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
            </div>
          </div>
          <div class="form-actions">
            <el-button data-testid="save-password" type="primary" @click="savePasswordChange">保存并重新登录</el-button>
          </div>
        </section>

        <RouterView v-slot="{ route }">
          <DashboardPanel
            v-if="route.name === 'dashboard'"
            :server-overview="serverOverview"
            :alert-summary="alertSummary"
            :metric-load-warning="metricLoadWarning"
            :loading="loading"
            @refresh="loadPlatformData"
            @navigate="(section: string) => void selectSection(section as SectionId)"
          />

          <DevicesPanel
            v-if="route.name === 'devices'"
            :remote-unavailable-reason="remoteUnavailableReason"
            @changed="refreshLogsAndOverview"
            @ssh="(device: Device) => openSshFromDevice(device)"
            @vnc="(device: Device) => openVncFromDevice(device)"
            @open-files="(device: Device) => openFilePanel(device)"
          />

          <FilesPanel
            v-if="route.name === 'files'"
            :loading="loading"
            @refresh="loadPlatformData"
          />

          <GroupsPanel
            v-if="route.name === 'groups'"
            @changed="refreshLogsAndOverview"
            @view-devices="selectGroup"
          />

          <RemotePanel v-if="route.name === 'remote'" />

          <UpdatesPanel
            v-if="route.name === 'updates'"
            :confirm-real-ssh-task="confirmRealSshTask"
            :target-summary-for-filter="targetSummaryForFilter"
            :target-summary-for-task="targetSummaryForTask"
            @changed="refreshLogsAndOverview"
          />

          <ScheduledTaskPanel v-if="route.name === 'scheduled'" :can-manage="isAdmin" />

          <AlertCenterPanel v-if="route.name === 'alerts'" :can-manage="isAdmin" />

          <SystemSettingsPanel v-if="route.name === 'settings' && isAdmin" />

          <UserManagementPanel v-if="route.name === 'users' && isAdmin" />

          <LogsPanel v-if="route.name === 'logs'" />

          <DiagnosticsPanel
            v-if="route.name === 'diagnostics'"
            :config="diagnosticsConfig"
            :loading="diagnosticsLoading"
            @refresh="loadDiagnosticsConfig"
          />
        </RouterView>
  </LayoutShell>
</template>
