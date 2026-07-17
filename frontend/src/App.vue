<script setup lang="ts">
import {
  Cpu,
  Collection,
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { storeToRefs } from "pinia";

import {
  AUTH_EXPIRED_EVENT,
  changePassword,
  clearAuthTokens,
  loginAdmin,
  setAuthTokens,
} from "./api/platform";
import { useAuthStore } from "./stores/auth";
import { useLogsStore } from "./stores/logs";
import { usePlatformDataStore } from "./stores/platformData";
import { usePlatformOverviewStore } from "./stores/platformOverview";
import { useUpdatesStore } from "./stores/updates";
import AppSidebar from "./components/AppSidebar.vue";
import AppTopbar from "./components/AppTopbar.vue";
import LayoutShell from "./components/LayoutShell.vue";

type SectionId = "dashboard" | "devices" | "projects" | "groups" | "remote" | "files" | "updates" | "scheduled" | "alerts" | "users" | "logs" | "diagnostics" | "settings";

const navItems: Array<{ id: SectionId; label: string; icon: Component; group: "overview" | "operations" | "governance"; adminOnly?: boolean }> = [
  { id: "dashboard", label: "仪表盘", icon: Monitor, group: "overview" },
  { id: "devices", label: "设备管理", icon: Cpu, group: "operations" },
  { id: "projects", label: "项目与功能", icon: Collection, group: "operations", adminOnly: true },
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
const logsStore = useLogsStore();
const { prependLocalLog } = logsStore;
const platformDataStore = usePlatformDataStore();
const { loading, operationError } = storeToRefs(platformDataStore);
const { loadPlatformData, clearPlatformData, setOperationError, clearOperationError } = platformDataStore;
const platformOverviewStore = usePlatformOverviewStore();
const {
  diagnosticsConfig,
  backendHealthStatus,
  backendHealthDetail,
} = storeToRefs(platformOverviewStore);
const {
  loadBackendHealth,
} = platformOverviewStore;
const updatesStore = useUpdatesStore();
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

const passwordForm = reactive({
  old_password: "",
  new_password: "",
  confirm_password: "",
});

const visibleNavItems = computed(() => navItems.filter((item) => !item.adminOnly || isAdmin.value));
const activeSectionTitle = computed(() => {
  const routeLabel = route.meta.label;
  return typeof routeLabel === "string" ? routeLabel : navItems.find((item) => item.id === activeSection.value)?.label ?? "仪表盘";
});
const currentRoleLabel = computed(() => (isAdmin.value ? "管理员" : "运维人员"));
const schedulerRunning = computed(() => diagnosticsConfig.value?.scheduler.running ?? null);

function adminOnlyMessage(section: SectionId): string {
  if (section === "projects") return "当前账号无权限访问项目与功能。";
  if (section === "users") return "当前账号无权限访问用户管理。";
  return "当前账号无权限访问系统设置。";
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
  loginPassword.value = "";
  clearPlatformData();
}

function handleAuthExpired() {
  logout();
  setOperationError("登录状态已过期，请重新登录。");
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

async function selectSection(section: SectionId) {
  if ((section === "users" || section === "settings" || section === "projects") && !isAdmin.value) {
    setOperationError(adminOnlyMessage(section));
    return;
  }
  clearOperationError();
  await router.push({ name: section });
}

watch([authenticated, currentUser, activeSection], ([isAuthenticated, user, section]) => {
  const navItem = navItems.find((item) => item.id === section);
  if (isAuthenticated && user && navItem?.adminOnly && user.role !== "admin") {
    setOperationError(adminOnlyMessage(section));
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

        <RouterView />
  </LayoutShell>
</template>
