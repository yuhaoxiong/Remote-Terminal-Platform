<script setup lang="ts">
import {
  Cpu,
  Document,
  Finished,
  FolderOpened,
  Monitor,
  Operation,
  Setting,
  UserFilled,
  VideoPlay,
  WarningFilled,
} from "@element-plus/icons-vue";
import { ElMessageBox } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import {
  AUTH_EXPIRED_EVENT,
  changePassword,
  clearAuthTokens,
  getCurrentUser,
  listDevices,
  listDeviceMetrics,
  listGroups,
  listUpdateTasks,
  loginAdmin,
  setAuthTokens,
  type CurrentUserResponse,
  type DeviceMetricRead,
  type ListLogsParams,
  type UpdateTaskRead,
} from "./api/platform";
import { useAuthStore } from "./stores/auth";
import { useDevicesStore, mapDevice, normalizeDeviceStatus, type Device } from "./stores/devices";
import { useGroupsStore, mapGroup, groupNameFor } from "./stores/groups";
import { useLogsStore, type AuditLog } from "./stores/logs";
import { usePlatformOverviewStore } from "./stores/platformOverview";
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
import GroupsPanel from "./components/GroupsPanel.vue";
import LayoutShell from "./components/LayoutShell.vue";
import LogsPanel from "./components/LogsPanel.vue";
import ScheduledTaskPanel from "./components/ScheduledTaskPanel.vue";
import SystemSettingsPanel from "./components/SystemSettingsPanel.vue";
import UpdatesPanel from "./components/UpdatesPanel.vue";
import UserManagementPanel from "./components/UserManagementPanel.vue";
import DashboardView from "./views/DashboardView.vue";
import DevicesView from "./views/DevicesView.vue";
import DiagnosticsView from "./views/DiagnosticsView.vue";
import FilesView from "./views/FilesView.vue";
import RemoteView from "./views/RemoteView.vue";

type SectionId = "dashboard" | "devices" | "groups" | "remote" | "files" | "updates" | "scheduled" | "alerts" | "users" | "logs" | "diagnostics" | "settings";

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
  visibleDevices,
} = storeToRefs(devicesStore);
const groupsStore = useGroupsStore();
const { groups } = storeToRefs(groupsStore);
const { recalculateGroupCounts } = groupsStore;
const logsStore = useLogsStore();
const { auditLogs, auditLogsTotal } = storeToRefs(logsStore);
const { mapLog, prependLocalLog } = logsStore;
const platformOverviewStore = usePlatformOverviewStore();
const {
  diagnosticsConfig,
  backendHealthStatus,
  backendHealthDetail,
} = storeToRefs(platformOverviewStore);
const {
  loadBackendHealth,
  refreshOverview,
  setMetricLoadWarning,
} = platformOverviewStore;
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

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
});


const deviceStatusText: Record<string, string> = {
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

const visibleNavItems = computed(() => navItems.filter((item) => !item.adminOnly || isAdmin.value));
const activeSectionTitle = computed(() => {
  const routeLabel = route.meta.label;
  return typeof routeLabel === "string" ? routeLabel : navItems.find((item) => item.id === activeSection.value)?.label ?? "仪表盘";
});
const currentRoleLabel = computed(() => (isAdmin.value ? "管理员" : "运维人员"));
const schedulerRunning = computed(() => diagnosticsConfig.value?.scheduler.running ?? null);

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
  setMetricLoadWarning(failedCount > 0 ? `有 ${failedCount} 台设备指标加载失败` : "");
  return enriched;
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
    const [userResponse, groupResponse, deviceResponse, updateResponse] = await Promise.all([
      getCurrentUser(),
      listGroups(),
      listDevices(),
      listUpdateTasks(),
      refreshOverview(),
    ]);
    currentUser.value = userResponse;
    const mappedGroups = groupResponse.items.map((group) => mapGroup(group, []));
    const mappedDevices = deviceResponse.items.map((device) => mapDevice(device, mappedGroups));
    devices.value = await attachLatestMetrics(mappedDevices);
    groups.value = groupResponse.items.map((group) => mapGroup(group, devices.value));
    updateTasks.value = updateResponse.items.map(mapUpdateTask);
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
  await refreshOverview();
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
  platformOverviewStore.reset();
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
  updatesStore.stopAllProgress();
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
          <DashboardView
            v-if="route.name === 'dashboard'"
            :loading="loading"
            @refresh="loadPlatformData"
            @navigate="(section: string) => void selectSection(section as SectionId)"
          />

          <DevicesView v-if="route.name === 'devices'" />

          <FilesView
            v-if="route.name === 'files'"
            :loading="loading"
            @refresh="loadPlatformData"
          />

          <GroupsPanel
            v-if="route.name === 'groups'"
            @changed="refreshLogsAndOverview"
            @view-devices="selectGroup"
          />

          <RemoteView v-if="route.name === 'remote'" />

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

          <DiagnosticsView v-if="route.name === 'diagnostics'" />
        </RouterView>
  </LayoutShell>
</template>
