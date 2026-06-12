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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, type Component } from "vue";
import { storeToRefs } from "pinia";

import {
  AUTH_EXPIRED_EVENT,
  buildApiWebSocketUrl,
  cancelUpdateTask,
  changePassword,
  clearAuthTokens,
  createDevice,
  createGroup,
  createUpdateTask,
  deleteGroup,
  deleteDevice,
  executeUpdateTask,
  exportLogs,
  exportUpdateTaskResults,
  getAlertSummary,
  getAccessToken,
  getCurrentUser,
  getDeviceStatus,
  getDiagnosticsConfig,
  getMonitoringOverview,

  importFrpsDevices,
  listDevices,
  listDeviceMetrics,
  listGroups,
  listLogs,
  listUpdateTasks,
  loginAdmin,
  openSshSession,
  openVncSession,
  type UpdateTaskTargetPreviewResponse,
  setAuthTokens,
  syncDeviceConfig,
  updateDevice,
  updateGroup,
  type AlertSummaryResponse,
  type CurrentUserResponse,
  type DiagnosticsConfigResponse,
  type DeviceCreateRequest,
  type DeviceMetricRead,
  type DeviceRead,
  type DeviceUpdateRequest,
  type FrpsDiscoveredDevice,
  type FrpsImportRequest,
  type GroupCreateRequest,
  type GroupRead,
  type GroupUpdateRequest,
  type ListLogsParams,
  type MonitoringOverviewResponse,
  type OperationLogRead,
  type UpdateTaskCreateRequest,
  type UpdateTaskDeviceRead,
  type UpdateTaskRead,
  type UpdateTaskTemplateRead,
} from "./api/platform";
import { fetchHealth } from "./api/health";
import { useAuthStore } from "./stores/auth";
import { useDevicesStore, type Device, type DeviceStatus } from "./stores/devices";
import { useGroupsStore, type Group } from "./stores/groups";
import { formatTime } from "./utils/format";
import AlertCenterPanel from "./components/AlertCenterPanel.vue";
import AppSidebar from "./components/AppSidebar.vue";
import AppTopbar from "./components/AppTopbar.vue";
import DeviceDetailDrawer from "./components/DeviceDetailDrawer.vue";
import DeviceFilePanel from "./components/DeviceFilePanel.vue";
import DeviceTargetSelector from "./components/DeviceTargetSelector.vue";
import DiagnosticsPanel from "./components/DiagnosticsPanel.vue";
import LayoutShell from "./components/LayoutShell.vue";
import MetricCard from "./components/MetricCard.vue";
import OperationLogDetailDrawer from "./components/OperationLogDetailDrawer.vue";
import ScheduledTaskPanel from "./components/ScheduledTaskPanel.vue";
import SystemSettingsPanel from "./components/SystemSettingsPanel.vue";
import UserManagementPanel from "./components/UserManagementPanel.vue";
import UpdateTaskResultTable from "./components/UpdateTaskResultTable.vue";
import UpdateTaskTemplatePanel from "./components/UpdateTaskTemplatePanel.vue";

type SectionId = "dashboard" | "devices" | "groups" | "remote" | "files" | "updates" | "scheduled" | "alerts" | "users" | "logs" | "diagnostics" | "settings";
type UpdateStatus = "pending" | "running" | "completed" | "canceled" | "partial_failed";
type ExecutionMode = "dry_run" | "ssh_command";

interface UpdateTask {
  id: number;
  name: string;
  command: string;
  target_filter: Record<string, unknown>;
  project_id: string;
  execution_mode: ExecutionMode;
  failure_strategy: "continue" | "pause" | "rollback";
  concurrency_limit: number;
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
const { devices } = storeToRefs(devicesStore);
const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const activeSection = ref<SectionId>("dashboard");

const loginUsername = ref("admin");
const loginPassword = ref("");
const loginError = ref("");
const deviceSearch = ref("");
const selectedGroupId = ref<number | null>(null);
const deviceStatusFilter = ref<DeviceStatus | "">("");
const deviceProjectFilter = ref("");
const deviceTagFilter = ref("");
const deviceCreateOpen = ref(false);
const deviceEditId = ref<number | null>(null);
const deviceDetailOpen = ref(false);
const deviceDetail = ref<Device | null>(null);
const frpsImportOpen = ref(false);
const frpsImporting = ref(false);
const frpsImportResult = ref("");
const updateCreateOpen = ref(false);
const passwordChangeOpen = ref(false);
const groupFormOpen = ref(false);
const groupEditId = ref<number | null>(null);
const loading = ref(false);
const operationError = ref("");
const remoteDeviceSearch = ref("");
const selectedRemoteDeviceId = ref<number | null>(null);
const sshTerminalHostRef = ref<HTMLElement | null>(null);
const vncCanvasHostRef = ref<HTMLElement | null>(null);
const filePanelDevice = ref<Device | null>(null);

const deviceForm = reactive({
  name: "",
  device_sn: "",
  project_id: "",
  group_id: null as number | null,
  location: "",
  tags: "",
  ssh_user: "ztl",
  ssh_auth_type: "password",
  ssh_password: "",
});

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
});

const groupForm = reactive({
  name: "",
  parent_id: null as number | null,
  description: "",
});

const updateForm = reactive({
  name: "",
  command: "",
  project_id: "",
  target_filter: {} as Record<string, unknown>,
  execution_mode: "dry_run" as ExecutionMode,
  failure_strategy: "continue" as "continue" | "pause" | "rollback",
  concurrency_limit: 5,
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

const updateTasks = ref<UpdateTask[]>([]);
const updateTargetPreview = ref<UpdateTaskTargetPreviewResponse | null>(null);
const auditLogs = ref<AuditLog[]>([]);
const selectedAuditLog = ref<AuditLog | null>(null);
const auditLogDetailOpen = ref(false);
const auditLogsTotal = ref(0);
const frpsImportItems = ref<FrpsDiscoveredDevice[]>([]);
const serverOverview = ref<MonitoringOverviewResponse | null>(null);
const alertSummary = ref<AlertSummaryResponse | null>(null);
const diagnosticsConfig = ref<DiagnosticsConfigResponse | null>(null);
const diagnosticsLoading = ref(false);
const backendHealthStatus = ref<"checking" | "healthy" | "failed">("checking");
const backendHealthDetail = ref("检测中");
const syncConfigOpen = ref(false);
const syncConfigTitle = ref("");
const syncConfigText = ref("");
const remoteSessions = reactive<Record<string, RemoteSessionUi>>({});
const sshSockets = new Map<number, WebSocket>();
const updateProgressSockets = new Map<number, WebSocket>();
const sshTerminals = new Map<number, SshTerminalHandle>();
const vncClients = new Map<number, VncClient>();

const logFilters = reactive({
  action: "",
  target_type: "",
  status: "",
});

const logPagination = reactive({
  offset: 0,
  limit: 50,
});

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

const METRIC_STALE_THRESHOLD_MS = 10 * 60 * 1000;
const CPU_HIGH_THRESHOLD = 90;
const MEMORY_HIGH_THRESHOLD = 85;
const DISK_HIGH_THRESHOLD = 90;

const metricLoadWarning = ref("");
const statusChartRef = ref<HTMLElement | null>(null);
const riskChartRef = ref<HTMLElement | null>(null);
let statusChart: { setOption: (options: unknown) => void; resize: () => void; dispose: () => void } | null = null;
let riskChart: { setOption: (options: unknown) => void; resize: () => void; dispose: () => void } | null = null;


const visibleNavItems = computed(() => navItems.filter((item) => !item.adminOnly || isAdmin.value));
const activeSectionTitle = computed(() => navItems.find((item) => item.id === activeSection.value)?.label ?? "仪表盘");
const currentRoleLabel = computed(() => (isAdmin.value ? "管理员" : "运维人员"));
const schedulerRunning = computed(() => diagnosticsConfig.value?.scheduler.running ?? null);

const visibleDevices = computed(() => {
  const keyword = deviceSearch.value.trim().toLowerCase();
  const projectKeyword = deviceProjectFilter.value.trim().toLowerCase();
  const tagKeyword = deviceTagFilter.value.trim().toLowerCase();
  return devices.value.filter((device) => {
    const matchesGroup = selectedGroupId.value === null || device.group_id === selectedGroupId.value;
    const matchesStatus = !deviceStatusFilter.value || device.status === deviceStatusFilter.value;
    const matchesProject = !projectKeyword || device.project_id.toLowerCase().includes(projectKeyword);
    const matchesTag = !tagKeyword || device.tags.some((tag) => tag.toLowerCase().includes(tagKeyword));
    const matchesKeyword =
      !keyword ||
      [device.name, device.device_sn, device.project_id, device.group, device.tags.join(",")]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    return matchesGroup && matchesStatus && matchesProject && matchesTag && matchesKeyword;
  });
});

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

const deviceFormTitle = computed(() => (deviceEditId.value === null ? "创建设备" : "编辑设备"));
const groupFormTitle = computed(() => (groupEditId.value === null ? "创建分组" : "编辑分组"));
const selectedGroupName = computed(() => groupNameFor(selectedGroupId.value));
const updateInitialDeviceIds = computed(() => {
  const deviceIds = updateForm.target_filter.device_ids;
  return Array.isArray(deviceIds) ? deviceIds.filter((id): id is number => typeof id === "number") : [];
});

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

const pendingTaskCount = computed(() => updateTasks.value.filter((task) => ["pending", "running"].includes(task.status)).length);

const abnormalDevices = computed(() => {
  const items: Array<{ key: string; device: Device; type: string; description: string; tagType: "danger" | "warning" | "info" }> = [];
  for (const device of devices.value) {
    if (device.status === "offline") {
      items.push({ key: `${device.id}-offline`, device, type: "离线", description: "设备当前处于离线状态", tagType: "danger" });
    } else if (device.status === "unknown") {
      items.push({ key: `${device.id}-unknown`, device, type: "未知", description: "设备状态暂不可确认", tagType: "info" });
    }
    if (device.metricLoadFailed) {
      items.push({ key: `${device.id}-metric-failed`, device, type: "指标失败", description: "最新指标读取失败", tagType: "warning" });
      continue;
    }
    if (device.metricStale) {
      items.push({ key: `${device.id}-stale`, device, type: "指标过期", description: "最新指标超过 10 分钟未更新", tagType: "warning" });
    }
    if (device.cpu !== null && device.cpu >= CPU_HIGH_THRESHOLD) {
      items.push({ key: `${device.id}-cpu`, device, type: "高负载", description: `CPU ${device.cpu}%`, tagType: "danger" });
    }
    if (device.memory !== null && device.memory >= MEMORY_HIGH_THRESHOLD) {
      items.push({ key: `${device.id}-memory`, device, type: "高内存", description: `内存 ${device.memory}%`, tagType: "warning" });
    }
    if (device.disk !== null && device.disk >= DISK_HIGH_THRESHOLD) {
      items.push({ key: `${device.id}-disk`, device, type: "磁盘紧张", description: `磁盘 ${device.disk}%`, tagType: "danger" });
    }
  }
  return items.slice(0, 8);
});

const statusDistribution = computed(() => {
  const online = devices.value.filter((device) => device.status === "online").length;
  const offline = devices.value.filter((device) => device.status === "offline").length;
  const unknown = devices.value.filter((device) => device.status === "unknown").length;
  return [
    { name: "在线", value: online },
    { name: "离线", value: offline },
    { name: "未知", value: unknown },
    { name: "异常", value: abnormalDevices.value.length },
  ];
});

const resourceRiskDistribution = computed(() => {
  let normal = 0;
  let highCpu = 0;
  let highMemory = 0;
  let highDisk = 0;
  let noMetric = 0;
  for (const device of devices.value) {
    if (device.metricLoadFailed || device.metricRecordedAt === null) {
      noMetric += 1;
      continue;
    }
    if (device.cpu !== null && device.cpu >= CPU_HIGH_THRESHOLD) {
      highCpu += 1;
    }
    if (device.memory !== null && device.memory >= MEMORY_HIGH_THRESHOLD) {
      highMemory += 1;
    }
    if (device.disk !== null && device.disk >= DISK_HIGH_THRESHOLD) {
      highDisk += 1;
    }
    if (
      (device.cpu === null || device.cpu < CPU_HIGH_THRESHOLD) &&
      (device.memory === null || device.memory < MEMORY_HIGH_THRESHOLD) &&
      (device.disk === null || device.disk < DISK_HIGH_THRESHOLD)
    ) {
      normal += 1;
    }
  }
  return [
    { name: "正常", value: normal },
    { name: "CPU 高", value: highCpu },
    { name: "内存高", value: highMemory },
    { name: "磁盘高", value: highDisk },
    { name: "无指标", value: noMetric },
  ];
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

function metricPercent(value: number | null): number {
  if (value === null || Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function metricText(value: number | null): string {
  return value === null ? "暂无指标" : `${metricPercent(value)}%`;
}

function hasMetric(device: Device): boolean {
  return device.cpu !== null || device.memory !== null || device.disk !== null;
}

function isMetricStale(recordedAt: string | null): boolean {
  if (!recordedAt) {
    return false;
  }
  const timestamp = new Date(recordedAt).getTime();
  if (Number.isNaN(timestamp)) {
    return false;
  }
  return Date.now() - timestamp > METRIC_STALE_THRESHOLD_MS;
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
    metricStale: isMetricStale(metric.recorded_at),
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
    cpu: null,
    memory: null,
    disk: null,
    metricRecordedAt: null,
    metricStale: false,
    metricLoadFailed: false,
  };
}

function mapGroup(group: GroupRead, sourceDevices = devices.value): Group {
  return {
    id: group.id,
    name: group.name,
    parent_id: group.parent_id,
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
    target_filter: targetFilter,
    project_id: projectId,
    execution_mode: task.execution_mode,
    failure_strategy: task.failure_strategy as "continue" | "pause" | "rollback",
    concurrency_limit: task.concurrency_limit,
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

function logQueryParams(): ListLogsParams {
  return {
    offset: logPagination.offset,
    limit: logPagination.limit,
    action: logFilters.action || undefined,
    target_type: logFilters.target_type || undefined,
    status: logFilters.status || undefined,
  };
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
  activeSection.value = "files";
}

function openDeviceDetail(device: Device) {
  deviceDetail.value = device;
  deviceDetailOpen.value = true;
}

function selectRemoteDevice(device: Device) {
  selectedRemoteDeviceId.value = device.id;
}

async function openSshFromDevice(device: Device) {
  selectRemoteDevice(device);
  activeSection.value = "remote";
  await nextTick();
  await startSshSession(device);
}

async function openVncFromDevice(device: Device) {
  selectRemoteDevice(device);
  activeSection.value = "remote";
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

function pieChartOptions(title: string, data: Array<{ name: string; value: number }>) {
  return {
    title: {
      text: title,
      left: "center",
      top: 0,
      textStyle: {
        fontSize: 13,
        fontWeight: 600,
        color: "#334155",
      },
    },
    tooltip: {
      trigger: "item",
    },
    legend: {
      bottom: 0,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: {
        color: "#64748b",
      },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "48%"],
        avoidLabelOverlap: true,
        label: {
          formatter: "{b}: {c}",
        },
        data,
      },
    ],
  };
}

async function renderDashboardCharts() {
  if (import.meta.env.MODE === "test" || activeSection.value !== "dashboard") {
    return;
  }
  await nextTick();
  if (!statusChartRef.value || !riskChartRef.value) {
    return;
  }
  const echarts = await import("echarts");
  statusChart ??= echarts.init(statusChartRef.value);
  riskChart ??= echarts.init(riskChartRef.value);
  statusChart.setOption(pieChartOptions("设备状态分布", statusDistribution.value));
  riskChart.setOption(pieChartOptions("资源风险分布", resourceRiskDistribution.value));
}

async function loadPlatformData() {
  loading.value = true;
  operationError.value = "";
  try {
    const [userResponse, groupResponse, deviceResponse, logResponse, updateResponse, overviewResponse, alertSummaryResponse] = await Promise.all([
      getCurrentUser(),
      listGroups(),
      listDevices(),
      listLogs(logQueryParams()),
      listUpdateTasks(),
      getMonitoringOverview(),
      getAlertSummary(),
    ]);
    currentUser.value = userResponse;
    const mappedGroups = groupResponse.items.map((group) => mapGroup(group, []));
    const mappedDevices = deviceResponse.items.map((device) => mapDevice(device, mappedGroups));
    devices.value = await attachLatestMetrics(mappedDevices);
    groups.value = groupResponse.items.map((group) => mapGroup(group, devices.value));
    auditLogs.value = logResponse.items.map(mapLog);
    auditLogsTotal.value = logResponse.total;
    updateTasks.value = updateResponse.items.map(mapUpdateTask);
    serverOverview.value = overviewResponse;
    alertSummary.value = alertSummaryResponse;
    void renderDashboardCharts();
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
  const [logResponse, overviewResponse, alertSummaryResponse] = await Promise.all([
    listLogs(logQueryParams()),
    getMonitoringOverview(),
    getAlertSummary(),
  ]);
  auditLogs.value = logResponse.items.map(mapLog);
  auditLogsTotal.value = logResponse.total;
  serverOverview.value = overviewResponse;
  alertSummary.value = alertSummaryResponse;
}

async function loadLogs() {
  const logResponse = await listLogs(logQueryParams());
  auditLogs.value = logResponse.items.map(mapLog);
  auditLogsTotal.value = logResponse.total;
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

function openGroupCreate() {
  groupEditId.value = null;
  Object.assign(groupForm, {
    name: "",
    parent_id: null,
    description: "",
  });
  groupFormOpen.value = true;
}

function openGroupEdit(group: Group) {
  groupEditId.value = group.id;
  Object.assign(groupForm, {
    name: group.name,
    parent_id: group.parent_id,
    description: group.description === "暂无描述" ? "" : group.description,
  });
  groupFormOpen.value = true;
}

async function saveGroup() {
  if (!groupForm.name) {
    prependLocalLog("分组校验", "分组", "blocked", "分组名称为必填项");
    return;
  }
  try {
    if (groupEditId.value === null) {
      const payload: GroupCreateRequest = {
        name: groupForm.name,
        parent_id: groupForm.parent_id,
        description: groupForm.description || undefined,
      };
      const created = await createGroup(payload);
      groups.value.push(mapGroup(created));
    } else {
      const payload: GroupUpdateRequest = {
        name: groupForm.name,
        parent_id: groupForm.parent_id,
        description: groupForm.description || undefined,
      };
      const updated = await updateGroup(groupEditId.value, payload);
      const index = groups.value.findIndex((group) => group.id === updated.id);
      if (index >= 0) {
        groups.value[index] = mapGroup(updated);
      }
      devices.value = devices.value.map((device) =>
        device.group_id === updated.id ? { ...device, group: updated.name } : device,
      );
    }
    recalculateGroupCounts();
    await refreshLogsAndOverview();
    groupFormOpen.value = false;
  } catch (error) {
    prependLocalLog(groupEditId.value === null ? "创建分组" : "编辑分组", "分组", "blocked", "保存分组失败，请检查后端返回。");
  }
}

async function removeGroup(group: Group) {
  try {
    await ElMessageBox.confirm(`确定删除分组 ${group.name}？`, "删除分组", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await deleteGroup(group.id);
    groups.value = groups.value.filter((item) => item.id !== group.id);
    if (selectedGroupId.value === group.id) {
      selectedGroupId.value = null;
    }
    devices.value = devices.value.map((device) =>
      device.group_id === group.id ? { ...device, group_id: null, group: "未分组" } : device,
    );
    await refreshLogsAndOverview();
  } catch (error) {
    prependLocalLog("删除分组", `分组：${group.id}`, "blocked", "删除分组失败，请检查后端返回。");
  }
}

function selectGroup(groupId: number | null) {
  selectedGroupId.value = groupId;
  activeSection.value = "devices";
}

function openDeviceCreate() {
  deviceEditId.value = null;
  Object.assign(deviceForm, {
    name: "",
    device_sn: "",
    project_id: "",
    group_id: selectedGroupId.value ?? groups.value[0]?.id ?? null,
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
    group_id: device.group_id,
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
    group_id: deviceForm.group_id,
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

async function showSyncConfig(device: Device) {
  syncConfigOpen.value = true;
  syncConfigTitle.value = `${device.name} 同步配置`;
  syncConfigText.value = "正在生成同步配置...";
  try {
    const response = await syncDeviceConfig(device.id);
    syncConfigText.value = response.config;
    await refreshLogsAndOverview();
  } catch (error) {
    syncConfigText.value = "生成同步配置失败，请检查设备远程端口配置。";
  }
}

async function copySyncConfig() {
  if (!syncConfigText.value || syncConfigText.value.startsWith("正在")) {
    return;
  }
  try {
    await navigator.clipboard?.writeText(syncConfigText.value);
    prependLocalLog("复制同步配置", "frpc", "success", "已复制到剪贴板");
  } catch {
    prependLocalLog("复制同步配置", "frpc", "blocked", "当前浏览器不支持自动复制，请手动选择配置内容");
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
  const defaultProjectId = devices.value[0]?.project_id ?? "";
  Object.assign(updateForm, {
    name: "",
    command: "hostname",
    project_id: defaultProjectId,
    target_filter: defaultProjectId ? { project_id: defaultProjectId } : {},
    execution_mode: "dry_run" as ExecutionMode,
    failure_strategy: "continue" as "continue" | "pause" | "rollback",
    concurrency_limit: 5,
  });
  updateTargetPreview.value = null;
  updateCreateOpen.value = true;
}

function handleUpdateTargetChange(targetFilter: Record<string, unknown>) {
  updateForm.target_filter = targetFilter;
  updateForm.project_id = typeof targetFilter.project_id === "string" ? targetFilter.project_id : "";
}

function handleUpdateTargetPreview(preview: UpdateTaskTargetPreviewResponse | null) {
  updateTargetPreview.value = preview;
}

function applyUpdateTemplate(template: UpdateTaskTemplateRead) {
  if (!isAdmin.value && template.default_execution_mode === "ssh_command") {
    prependLocalLog("套用命令模板", `模板：${template.id}`, "blocked", "当前账号无权限套用真实 SSH 命令模板。");
    return;
  }
  updateForm.command = template.command;
  updateForm.execution_mode = template.default_execution_mode;
  if (!updateForm.name) {
    updateForm.name = template.name;
  }
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

function updateTaskFromSnapshot(snapshot: UpdateTaskRead) {
  const mapped = mapUpdateTask(snapshot);
  const index = updateTasks.value.findIndex((item) => item.id === mapped.id);
  if (index >= 0) {
    updateTasks.value[index] = mapped;
  } else {
    updateTasks.value.push(mapped);
  }
  if (mapped.status !== "running") {
    stopUpdateProgress(mapped.id);
  }
}

function startUpdateProgress(taskId: number) {
  if (typeof WebSocket === "undefined") {
    return;
  }
  stopUpdateProgress(taskId);
  const token = getAccessToken();
  if (!token) {
    return;
  }
  const websocketUrl = buildApiWebSocketUrl(`/api/ws/update-tasks/${taskId}`, token);
  const socket = new WebSocket(websocketUrl);
  updateProgressSockets.set(taskId, socket);
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(String(event.data)) as { type?: string; task?: UpdateTaskRead };
      if (payload.type === "task.snapshot" && payload.task) {
        updateTaskFromSnapshot(payload.task);
      }
    } catch {
      const task = updateTasks.value.find((item) => item.id === taskId);
      if (task) {
        task.lastEvent = "更新任务进度消息解析失败";
      }
    }
  };
  socket.onerror = () => {
    const task = updateTasks.value.find((item) => item.id === taskId);
    if (task && task.status === "running") {
      task.lastEvent = "实时进度连接异常，仍可刷新任务状态";
    }
  };
  socket.onclose = () => {
    if (updateProgressSockets.get(taskId) === socket) {
      updateProgressSockets.delete(taskId);
    }
  };
}

function stopUpdateProgress(taskId: number) {
  const socket = updateProgressSockets.get(taskId);
  if (!socket) {
    return;
  }
  updateProgressSockets.delete(taskId);
  socket.close();
}

async function saveUpdate() {
  if (!updateForm.name || !updateForm.command) {
    prependLocalLog("更新任务校验", "新任务", "blocked", "任务名称和命令为必填项");
    return;
  }
  if (!isAdmin.value && updateForm.execution_mode === "ssh_command") {
    updateForm.execution_mode = "dry_run";
    prependLocalLog("更新任务校验", "新任务", "blocked", "当前账号无权创建真实 SSH 任务，已切换为演练模式。");
    return;
  }
  const targetFilter = updateForm.target_filter && Object.keys(updateForm.target_filter).length > 0
    ? updateForm.target_filter
    : updateForm.project_id
      ? { project_id: updateForm.project_id }
      : {};
  if (updateForm.execution_mode === "ssh_command" && updateTargetPreview.value?.total === 0) {
    prependLocalLog("更新任务校验", "新任务", "blocked", "目标预览为空，未创建真实 SSH 任务。");
    return;
  }
  const payload: UpdateTaskCreateRequest = {
    name: updateForm.name,
    task_type: "command",
    command: updateForm.command,
    target_filter: targetFilter,
    execution_mode: updateForm.execution_mode,
    failure_strategy: updateForm.failure_strategy,
    concurrency_limit: Number(updateForm.concurrency_limit) || 1,
  };
  if (payload.execution_mode === "ssh_command") {
    const targetSummary = `${targetSummaryForFilter(targetFilter)}，预览 ${updateTargetPreview.value?.total ?? "未确认"} 台`;
    const confirmed = await confirmRealSshTask(updateForm.command, targetSummary);
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
    const confirmed = await confirmRealSshTask(task.command, targetSummaryForTask(task));
    if (!confirmed) {
      return;
    }
  }
  task.status = "running";
  task.lastEvent = "正在请求后端执行";
  startUpdateProgress(task.id);
  try {
    const executed = await executeUpdateTask(task.id);
    const mapped = mapUpdateTask(executed);
    const index = updateTasks.value.findIndex((item) => item.id === task.id);
    if (index >= 0) {
      updateTasks.value[index] = mapped;
    }
    startUpdateProgress(task.id);
    await refreshLogsAndOverview();
  } catch (error) {
    task.status = "partial_failed";
    task.lastEvent = "后端执行失败";
    stopUpdateProgress(task.id);
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
    stopUpdateProgress(task.id);
    await refreshLogsAndOverview();
  } catch (error) {
    prependLocalLog("取消更新任务", `更新任务：${task.id}`, "blocked", "取消任务失败，请检查后端任务状态。");
  }
}

function openRetryFailedTask(task: UpdateTask, deviceIds: number[]) {
  if (deviceIds.length === 0) {
    prependLocalLog("更新任务重试", `更新任务：${task.id}`, "blocked", "当前任务没有失败设备。");
    return;
  }
  Object.assign(updateForm, {
    name: `${task.name} 失败重试`,
    command: task.command,
    project_id: "",
    target_filter: { device_ids: deviceIds },
    execution_mode: task.execution_mode,
    failure_strategy: task.failure_strategy,
    concurrency_limit: task.concurrency_limit,
  });
  updateTargetPreview.value = null;
  updateCreateOpen.value = true;
}

async function downloadUpdateTaskResults(task: UpdateTask) {
  try {
    const blob = await exportUpdateTaskResults(task.id);
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `update_task_${task.id}_results.csv`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  } catch {
    prependLocalLog("导出更新结果", `更新任务：${task.id}`, "blocked", "导出失败，请检查后端服务。");
  }
}

async function applyLogFilters() {
  logPagination.offset = 0;
  await loadLogs();
}

async function handleLogPageChange(page: number) {
  logPagination.offset = (page - 1) * logPagination.limit;
  await loadLogs();
}

async function downloadLogs() {
  try {
    const blob = await exportLogs({
      action: logFilters.action || undefined,
      target_type: logFilters.target_type || undefined,
      status: logFilters.status || undefined,
    });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "operation_logs.csv";
    anchor.click();
    window.URL.revokeObjectURL(url);
  } catch {
    prependLocalLog("导出操作日志", "操作日志", "blocked", "导出 CSV 失败，请检查后端服务。");
  }
}

function openAuditLogDetail(log: AuditLog) {
  selectedAuditLog.value = log;
  auditLogDetailOpen.value = true;
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

function selectSection(section: SectionId) {
  if ((section === "users" || section === "settings") && !isAdmin.value) {
    operationError.value = section === "users" ? "当前账号无权限访问用户管理。" : "当前账号无权限访问系统设置。";
    return;
  }
  activeSection.value = section;
  if (section === "diagnostics") {
    void loadDiagnosticsConfig();
  }
  if (section === "dashboard") {
    void renderDashboardCharts();
  }
}

onMounted(() => {
  window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  void loadBackendHealth();
  if (authenticated.value) {
    void loadPlatformData();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired);
  statusChart?.dispose();
  riskChart?.dispose();
  for (const deviceId of sshSockets.keys()) {
    disconnectSshSession(deviceId);
  }
  for (const taskId of updateProgressSockets.keys()) {
    stopUpdateProgress(taskId);
  }
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
      <AppSidebar :active="activeSection" :items="visibleNavItems" @select="(id) => selectSection(id as SectionId)" />
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

        <section v-if="activeSection === 'dashboard'" class="page-section">
          <div class="stat-grid">
            <MetricCard label="设备总数" :value="overview.devices" unit="台" trend="统一纳管设备" :icon="Cpu" />
            <MetricCard label="在线设备" :value="overview.online" unit="台" tone="success" trend="可远程连接" :icon="Monitor" />
            <MetricCard label="离线/未知" :value="overview.degraded" unit="台" tone="warning" trend="需优先排查" :icon="WarningFilled" />
            <MetricCard label="活跃告警" :value="alertSummary?.active_count ?? 0" unit="条" tone="danger" trend="待确认或恢复" :icon="WarningFilled" />
            <MetricCard label="待执行任务" :value="pendingTaskCount" unit="个" tone="info" trend="批量或定时任务" :icon="Finished" />
          </div>

          <div class="two-column">
            <section class="panel">
              <div class="panel-header">
                <h3>资源快照</h3>
                <el-button :icon="Refresh" text :loading="loading" @click="loadPlatformData">刷新</el-button>
              </div>
              <el-alert
                v-if="metricLoadWarning"
                class="validation-alert"
                type="warning"
                show-icon
                :closable="false"
                :title="metricLoadWarning"
              />
              <div v-for="device in devices" :key="device.id" class="metric-row">
                <div class="metric-title">
                  <div>
                    <strong>{{ device.name }}</strong>
                    <span>{{ device.project_id }}</span>
                  </div>
                  <div class="metric-tags">
                    <el-tag size="small" :type="statusType[device.status]">{{ deviceStatusText[device.status] }}</el-tag>
                    <el-tag v-if="device.metricLoadFailed" size="small" type="warning">指标加载失败</el-tag>
                    <el-tag v-else-if="device.metricStale" size="small" type="warning">指标过期</el-tag>
                    <el-tag v-else-if="!hasMetric(device)" size="small" type="info">暂无指标</el-tag>
                  </div>
                </div>
                <div v-if="device.metricLoadFailed" class="metric-empty">指标加载失败</div>
                <div v-else-if="!hasMetric(device)" class="metric-empty">暂无指标</div>
                <div v-else class="metric-bars">
                  <div class="metric-bar">
                    <span>CPU {{ metricText(device.cpu) }}</span>
                    <el-progress :percentage="metricPercent(device.cpu)" :stroke-width="10" />
                  </div>
                  <div class="metric-bar">
                    <span>内存 {{ metricText(device.memory) }}</span>
                    <el-progress :percentage="metricPercent(device.memory)" :stroke-width="10" color="#4f46e5" />
                  </div>
                  <div class="metric-bar">
                    <span>磁盘 {{ metricText(device.disk) }}</span>
                    <el-progress :percentage="metricPercent(device.disk)" :stroke-width="10" color="#dc2626" />
                  </div>
                </div>
                <small>{{ device.metricRecordedAt ? `最近指标 ${formatTime(device.metricRecordedAt)}` : "未上报" }}</small>
              </div>
              <el-empty v-if="!devices.length" description="暂无设备" />
            </section>

            <section class="panel">
              <div class="panel-header">
                <h3>异常设备</h3>
                <el-button text @click="selectSection('devices')">进入设备管理</el-button>
              </div>
              <div v-if="abnormalDevices.length" class="alert-list">
                <div v-for="item in abnormalDevices" :key="item.key" class="alert-row">
                  <el-tag size="small" :type="item.tagType">{{ item.type }}</el-tag>
                  <div>
                    <strong>{{ item.device.name }}</strong>
                    <span>{{ item.device.project_id }} · {{ item.description }}</span>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无异常设备" />
            </section>
          </div>

          <div class="two-column chart-row">
            <section class="panel">
              <div class="panel-header">
                <h3>监控分布</h3>
              </div>
              <div v-if="devices.length" class="chart-grid">
                <div ref="statusChartRef" class="chart-box" aria-label="设备状态分布"></div>
                <div ref="riskChartRef" class="chart-box" aria-label="资源风险分布"></div>
                <div class="chart-summary">
                  <div v-for="item in statusDistribution" :key="item.name">
                    <span>{{ item.name }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                  <div v-for="item in resourceRiskDistribution" :key="item.name">
                    <span>{{ item.name }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无监控数据" />
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
          <div class="page-title-row">
            <div>
              <h3>设备管理</h3>
              <p class="muted">按项目、分组、状态和标签快速定位边缘设备。</p>
            </div>
            <div class="topbar-actions">
              <el-button data-testid="open-device-create" type="primary" :icon="Plus" @click="openDeviceCreate">
                新建设备
              </el-button>
              <el-button data-testid="open-frps-import" :icon="Refresh" @click="frpsImportOpen = !frpsImportOpen">
                frps 自动发现
              </el-button>
            </div>
          </div>

          <div class="filter-panel">
            <label class="field-label">
              <span>关键词</span>
              <el-input v-model="deviceSearch" :prefix-icon="Search" placeholder="设备名称 / SN / IP / 标签" />
            </label>
            <label class="field-label">
              <span>分组</span>
              <el-select v-model="selectedGroupId" placeholder="全部分组" clearable>
                <el-option v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" />
              </el-select>
            </label>
            <label class="field-label">
              <span>状态</span>
              <el-select v-model="deviceStatusFilter" placeholder="全部状态" clearable>
                <el-option label="在线" value="online" />
                <el-option label="离线" value="offline" />
                <el-option label="异常" value="degraded" />
                <el-option label="未知" value="unknown" />
              </el-select>
            </label>
            <label class="field-label">
              <span>标签</span>
              <el-input v-model="deviceTagFilter" placeholder="请输入标签" />
            </label>
            <label class="field-label">
              <span>项目号</span>
              <el-input v-model="deviceProjectFilter" placeholder="请输入项目号" />
            </label>
            <div class="filter-actions">
              <el-button
                @click="
                  deviceSearch = '';
                  selectedGroupId = null;
                  deviceStatusFilter = '';
                  deviceTagFilter = '';
                  deviceProjectFilter = '';
                "
              >
                重置
              </el-button>
              <el-button type="primary" :icon="Search">筛选</el-button>
            </div>
          </div>
          <el-alert
            v-if="selectedGroupId !== null"
            type="info"
            show-icon
            :closable="false"
            :title="`当前仅显示 ${selectedGroupName} 分组设备`"
          >
            <template #default>
              <el-button text @click="selectedGroupId = null">清除分组筛选</el-button>
            </template>
          </el-alert>

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
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="statusType[row.status as DeviceStatus]">{{ deviceStatusText[row.status as DeviceStatus] }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="project_id" label="项目号" width="130" />
              <el-table-column prop="group" label="分组" width="110" />
              <el-table-column prop="location" label="部署位置" min-width="130" />
              <el-table-column prop="ssh_port" label="SSH 端口" width="100" />
              <el-table-column prop="vnc_port" label="VNC 端口" width="100" />
              <el-table-column label="最近指标" min-width="150">
                <template #default="{ row }">
                  <span>{{ row.metricRecordedAt ? formatTime(row.metricRecordedAt) : "未上报" }}</span>
                </template>
              </el-table-column>
              <el-table-column label="标签" min-width="150">
                <template #default="{ row }">
                  <el-tag v-for="tag in row.tags" :key="tag" size="small" class="tag-chip">{{ tag }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="360" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" text @click="openDeviceDetail(row)">详情</el-button>
                  <el-tooltip :content="remoteUnavailableReason(row, 'ssh') || 'SSH 连接'" placement="top">
                    <el-button size="small" :disabled="Boolean(remoteUnavailableReason(row, 'ssh'))" @click="openSshFromDevice(row)">SSH</el-button>
                  </el-tooltip>
                  <el-tooltip :content="remoteUnavailableReason(row, 'vnc') || 'VNC 连接'" placement="top">
                    <el-button size="small" :disabled="Boolean(remoteUnavailableReason(row, 'vnc'))" @click="openVncFromDevice(row)">VNC</el-button>
                  </el-tooltip>
                  <el-button :data-testid="`open-files-${row.id}`" size="small" @click="openFilePanel(row)">文件</el-button>
                  <el-button :data-testid="`sync-device-${row.id}`" size="small" @click="showSyncConfig(row)">同步</el-button>
                  <el-button :data-testid="`refresh-device-${row.id}`" size="small" :icon="Refresh" @click="refreshDeviceStatus(row)">刷新</el-button>
                  <el-button :data-testid="`edit-device-${row.id}`" size="small" @click="openDeviceEdit(row)">编辑</el-button>
                  <el-button :data-testid="`delete-device-${row.id}`" size="small" type="danger" text @click="removeDevice(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <DeviceDetailDrawer
            v-model:visible="deviceDetailOpen"
            :device="deviceDetail"
            @ssh="(device) => openSshFromDevice(device)"
            @vnc="(device) => openVncFromDevice(device)"
            @files="(device) => openFilePanel(device)"
            @sync="(device) => showSyncConfig(device)"
            @edit="(device) => openDeviceEdit(device)"
            @remove="(device) => removeDevice(device)"
          />

          <section v-if="deviceCreateOpen" class="form-panel" :aria-label="deviceFormTitle">
            <div class="panel-header">
              <h3>{{ deviceFormTitle }}</h3>
              <el-button text @click="deviceCreateOpen = false">关闭</el-button>
            </div>
            <div class="form-grid">
              <div data-testid="device-name" class="input-wrap"><el-input v-model="deviceForm.name" placeholder="设备名称" /></div>
              <div data-testid="device-sn" class="input-wrap"><el-input v-model="deviceForm.device_sn" :disabled="deviceEditId !== null" placeholder="设备序列号" /></div>
              <div data-testid="device-project" class="input-wrap"><el-input v-model="deviceForm.project_id" placeholder="项目号" /></div>
              <el-select v-model="deviceForm.group_id" placeholder="选择分组" clearable>
                <el-option v-for="group in groups" :key="group.id" :label="group.name" :value="group.id" />
              </el-select>
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

          <section v-if="syncConfigOpen" class="form-panel" aria-label="frpc 同步配置">
            <div class="panel-header">
              <h3>{{ syncConfigTitle }}</h3>
              <el-button text @click="syncConfigOpen = false">关闭</el-button>
            </div>
            <pre class="terminal-output">{{ syncConfigText }}</pre>
            <div class="form-actions">
              <el-button data-testid="copy-sync-config" @click="copySyncConfig">复制配置</el-button>
            </div>
          </section>

          <DeviceFilePanel v-if="filePanelDevice" :device="filePanelDevice" />
        </section>

        <section v-if="activeSection === 'files'" class="page-section">
          <div class="page-title-row">
            <div>
              <h3>文件管理</h3>
              <p class="muted">选择设备后进行文件浏览、上传、下载和删除。</p>
            </div>
            <el-button :icon="Refresh" :loading="loading" @click="loadPlatformData">刷新设备</el-button>
          </div>
          <section class="panel">
            <div class="panel-header">
              <h3>选择设备</h3>
              <el-input v-model="deviceSearch" :prefix-icon="Search" placeholder="按设备名称、序列号、项目号搜索" />
            </div>
            <el-table :data="visibleDevices" row-key="id" empty-text="暂无可管理文件的设备">
              <el-table-column prop="name" label="设备名称" min-width="180" />
              <el-table-column prop="project_id" label="项目号" width="130" />
              <el-table-column prop="location" label="位置" min-width="130" />
              <el-table-column prop="ssh_port" label="SSH 端口" width="110" />
              <el-table-column label="凭据" width="110">
                <template #default="{ row }">
                  <el-tag :type="row.ssh_credential_configured ? 'success' : 'warning'">
                    {{ row.ssh_credential_configured ? "已配置" : "缺失" }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="140">
                <template #default="{ row }">
                  <el-button :data-testid="`open-files-${row.id}`" type="primary" text @click="openFilePanel(row)">打开文件</el-button>
                </template>
              </el-table-column>
            </el-table>
          </section>
          <DeviceFilePanel v-if="filePanelDevice" :device="filePanelDevice" />
          <el-empty v-else description="请选择一台设备开始文件管理" />
        </section>

        <section v-if="activeSection === 'groups'" class="page-section">
          <div class="toolbar">
            <div>
              <h3>分组管理</h3>
              <p class="muted">维护设备分组，并快速按分组进入设备列表。</p>
            </div>
            <el-button data-testid="open-group-create" type="primary" :icon="Plus" @click="openGroupCreate">新建分组</el-button>
          </div>

          <section v-if="groupFormOpen" class="form-panel" :aria-label="groupFormTitle">
            <div class="panel-header">
              <h3>{{ groupFormTitle }}</h3>
              <el-button text @click="groupFormOpen = false">关闭</el-button>
            </div>
            <div class="form-grid">
              <div data-testid="group-name" class="input-wrap"><el-input v-model="groupForm.name" placeholder="分组名称" /></div>
              <el-select v-model="groupForm.parent_id" placeholder="上级分组" clearable>
                <el-option
                  v-for="group in groups.filter((item) => item.id !== groupEditId)"
                  :key="group.id"
                  :label="group.name"
                  :value="group.id"
                />
              </el-select>
              <div data-testid="group-description" class="input-wrap textarea-wrap">
                <el-input v-model="groupForm.description" type="textarea" :rows="3" placeholder="分组描述" />
              </div>
            </div>
            <div class="form-actions">
              <el-button data-testid="save-group" type="primary" @click="saveGroup">保存分组</el-button>
            </div>
          </section>

          <div class="list-grid">
            <div v-for="group in groups" :key="group.id" class="item-card">
              <h3>{{ group.name }}</h3>
              <p>{{ group.description }}</p>
              <el-tag>{{ group.deviceCount }} 台设备</el-tag>
              <div class="form-actions">
                <el-button :data-testid="`filter-group-${group.id}`" size="small" @click="selectGroup(group.id)">查看设备</el-button>
                <el-button :data-testid="`edit-group-${group.id}`" size="small" @click="openGroupEdit(group)">编辑</el-button>
                <el-button :data-testid="`delete-group-${group.id}`" size="small" type="danger" @click="removeGroup(group)">删除</el-button>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeSection === 'remote'" class="page-section">
          <div class="remote-workspace">
            <aside class="remote-device-list" aria-label="远程设备列表">
              <div class="remote-list-header">
                <h3>远程设备</h3>
                <el-input
                  v-model="remoteDeviceSearch"
                  data-testid="remote-device-search"
                  :prefix-icon="Search"
                  placeholder="按名称、序列号或项目搜索"
                />
              </div>
              <button
                v-for="device in remoteVisibleDevices"
                :key="device.id"
                type="button"
                class="remote-device-row"
                :class="{ 'is-selected': selectedRemoteDeviceId === device.id }"
                :data-testid="`select-remote-device-${device.id}`"
                @click="selectRemoteDevice(device)"
              >
                <span>
                  <strong>{{ device.name }}</strong>
                  <small>{{ device.device_sn }} · {{ device.project_id }}</small>
                </span>
                <span class="remote-port-tags">
                  <el-tag size="small" :type="device.ssh_port ? 'success' : 'info'">SSH {{ device.ssh_port ?? "缺失" }}</el-tag>
                  <el-tag size="small" :type="device.vnc_port ? 'success' : 'info'">VNC {{ device.vnc_port ?? "缺失" }}</el-tag>
                </span>
              </button>
              <el-empty v-if="remoteVisibleDevices.length === 0" description="没有匹配的远程设备" />
            </aside>

            <section class="remote-console" aria-label="远程操作区">
              <el-empty v-if="!selectedRemoteDevice" description="请选择设备" />
              <template v-else>
                <div class="panel-header remote-console-header">
                  <div>
                    <h3>{{ selectedRemoteDevice.name }}</h3>
                    <p class="muted">
                      {{ selectedRemoteDevice.device_sn }} · {{ selectedRemoteDevice.location }} · {{ selectedRemoteDevice.group }}
                    </p>
                  </div>
                  <div class="remote-session-state">
                    <el-tag :type="statusType[selectedRemoteDevice.status]">{{ deviceStatusText[selectedRemoteDevice.status] }}</el-tag>
                    <el-tag :type="selectedRemoteDevice.ssh_credential_configured ? 'success' : 'warning'">
                      {{ selectedRemoteDevice.ssh_credential_configured ? "凭据已配置" : "凭据未配置" }}
                    </el-tag>
                  </div>
                </div>

                <el-tabs class="remote-tabs">
                  <el-tab-pane label="SSH 终端">
                    <section class="remote-panel">
                      <div class="panel-header">
                        <div>
                          <h3>SSH 终端</h3>
                          <p class="muted">{{ selectedSshSession?.message ?? "未连接" }}</p>
                        </div>
                        <div class="remote-actions">
                          <el-button
                            :data-testid="`open-ssh-${selectedRemoteDevice.id}`"
                            type="primary"
                            :icon="Monitor"
                            :disabled="!canOpenRemote(selectedRemoteDevice, 'ssh')"
                            :loading="selectedSshSession?.status === 'connecting'"
                            @click="startSshSession(selectedRemoteDevice)"
                          >
                            连接 SSH
                          </el-button>
                          <el-button
                            :data-testid="`disconnect-ssh-${selectedRemoteDevice.id}`"
                            :disabled="selectedSshSession?.status !== 'connected'"
                            @click="disconnectSshSession(selectedRemoteDevice.id)"
                          >
                            断开 SSH
                          </el-button>
                        </div>
                      </div>
                      <p v-if="remoteUnavailableReason(selectedRemoteDevice, 'ssh')" class="remote-warning">
                        {{ remoteUnavailableReason(selectedRemoteDevice, "ssh") }}
                      </p>
                      <div ref="sshTerminalHostRef" data-testid="ssh-terminal" class="ssh-terminal"></div>
                      <pre v-if="selectedSshSession?.output" data-testid="ssh-transcript" class="terminal-output">{{
                        selectedSshSession.output
                      }}</pre>
                    </section>
                  </el-tab-pane>
                  <el-tab-pane label="VNC 桌面">
                    <section class="remote-panel">
                      <div class="panel-header">
                        <div>
                          <h3>VNC 桌面</h3>
                          <p class="muted">{{ selectedVncSession?.message ?? "未连接" }}</p>
                        </div>
                        <div class="remote-actions">
                          <el-button
                            :data-testid="`open-vnc-${selectedRemoteDevice.id}`"
                            :icon="VideoPlay"
                            :disabled="!canOpenRemote(selectedRemoteDevice, 'vnc')"
                            :loading="selectedVncSession?.status === 'connecting'"
                            @click="startVncSession(selectedRemoteDevice)"
                          >
                            连接 VNC
                          </el-button>
                          <el-button
                            :data-testid="`disconnect-vnc-${selectedRemoteDevice.id}`"
                            :disabled="selectedVncSession?.status !== 'connected'"
                            @click="disconnectVncSession(selectedRemoteDevice.id)"
                          >
                            断开 VNC
                          </el-button>
                          <el-button
                            :data-testid="`fullscreen-vnc-${selectedRemoteDevice.id}`"
                            :disabled="selectedVncSession?.status !== 'connected'"
                            @click="requestVncFullscreen"
                          >
                            全屏
                          </el-button>
                        </div>
                      </div>
                      <p v-if="remoteUnavailableReason(selectedRemoteDevice, 'vnc')" class="remote-warning">
                        {{ remoteUnavailableReason(selectedRemoteDevice, "vnc") }}
                      </p>
                      <div ref="vncCanvasHostRef" data-testid="vnc-screen" class="vnc-screen">
                        <span v-if="selectedVncSession?.status !== 'connected'">VNC 画面将在连接后显示</span>
                      </div>
                    </section>
                  </el-tab-pane>
                  <el-tab-pane label="连接日志">
                    <section class="remote-panel">
                      <h3>连接日志</h3>
                      <div class="connection-log">
                        <p>SSH：{{ selectedSshSession?.message ?? "未连接" }}</p>
                        <p>VNC：{{ selectedVncSession?.message ?? "未连接" }}</p>
                        <p>远程端口：SSH {{ selectedRemoteDevice.ssh_port ?? "缺失" }} / VNC {{ selectedRemoteDevice.vnc_port ?? "缺失" }}</p>
                      </div>
                    </section>
                  </el-tab-pane>
                </el-tabs>
              </template>
            </section>
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
              <label class="field-label">
                <span>执行模式</span>
                <select data-testid="update-execution-mode" v-model="updateForm.execution_mode" class="native-select">
                  <option value="dry_run">演练模式</option>
                  <option v-if="isAdmin" value="ssh_command">真实 SSH 执行</option>
                </select>
              </label>
              <label class="field-label">
                <span>失败策略</span>
                <select data-testid="update-failure-strategy" v-model="updateForm.failure_strategy" class="native-select">
                  <option value="continue">继续执行</option>
                  <option value="pause">暂停后续</option>
                  <option value="rollback">预留回滚</option>
                </select>
              </label>
              <div data-testid="update-concurrency" class="input-wrap">
                <el-input v-model.number="updateForm.concurrency_limit" type="number" min="1" placeholder="并发数量" />
              </div>
              <div data-testid="update-command" class="input-wrap textarea-wrap">
                <el-input v-model="updateForm.command" type="textarea" :rows="3" placeholder="命令或脚本" />
              </div>
            </div>
            <UpdateTaskTemplatePanel :can-manage="isAdmin" @apply="applyUpdateTemplate" />
            <DeviceTargetSelector
              :devices="devices"
              :groups="groups"
              :execution-mode="updateForm.execution_mode"
              :initial-project-id="updateForm.project_id"
              :initial-device-ids="updateInitialDeviceIds"
              @target-change="handleUpdateTargetChange"
              @preview-change="handleUpdateTargetPreview"
            />
            <el-alert
              v-if="!isAdmin"
              class="validation-alert"
              type="info"
              show-icon
              :closable="false"
              title="当前账号为运维人员，仅允许创建和执行演练任务。"
            />
            <p v-if="updateForm.execution_mode === 'ssh_command'" class="risk-note">
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
                  <UpdateTaskResultTable :devices="row.devices" @retry-failed="(deviceIds) => openRetryFailedTask(row, deviceIds)" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="250">
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
                  <el-button :data-testid="`export-update-${row.id}`" size="small" @click="downloadUpdateTaskResults(row)">
                    导出
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

        <ScheduledTaskPanel v-if="activeSection === 'scheduled'" :can-manage="isAdmin" />

        <AlertCenterPanel v-if="activeSection === 'alerts'" :can-manage="isAdmin" />

        <SystemSettingsPanel v-if="activeSection === 'settings' && isAdmin" />

        <UserManagementPanel v-if="activeSection === 'users' && isAdmin" />

        <section v-if="activeSection === 'logs'" class="page-section">
          <div class="toolbar">
            <h3>操作日志</h3>
            <el-button data-testid="export-logs" :icon="Document" @click="downloadLogs">导出 CSV</el-button>
          </div>
          <div class="form-panel">
            <div class="form-grid">
              <div data-testid="log-action" class="input-wrap"><el-input v-model="logFilters.action" placeholder="操作，例如 device.create" /></div>
              <div data-testid="log-target-type" class="input-wrap"><el-input v-model="logFilters.target_type" placeholder="目标类型，例如 device" /></div>
              <div data-testid="log-status" class="input-wrap"><el-input v-model="logFilters.status" placeholder="状态，例如 success" /></div>
            </div>
            <div class="form-actions">
              <el-button data-testid="apply-log-filters" type="primary" @click="applyLogFilters">筛选</el-button>
            </div>
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
              <el-table-column label="操作" width="100" fixed="right">
                <template #default="{ row }">
                  <el-button :data-testid="`open-log-detail-${row.id}`" size="small" text @click="openAuditLogDetail(row)">详情</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-pagination
            layout="prev, pager, next, total"
            :total="auditLogsTotal"
            :page-size="logPagination.limit"
            :current-page="Math.floor(logPagination.offset / logPagination.limit) + 1"
            @current-change="handleLogPageChange"
          />
          <OperationLogDetailDrawer v-model="auditLogDetailOpen" :log="selectedAuditLog" />
          <span v-if="auditLogDetailOpen && selectedAuditLog" data-testid="selected-log-detail" class="visually-hidden">
            操作详情 {{ selectedAuditLog.detail }}
          </span>
        </section>

        <DiagnosticsPanel
          v-if="activeSection === 'diagnostics'"
          :config="diagnosticsConfig"
          :loading="diagnosticsLoading"
          @refresh="loadDiagnosticsConfig"
        />
  </LayoutShell>
</template>
