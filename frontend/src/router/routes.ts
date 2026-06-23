import type { RouteRecordRaw } from "vue-router";

import DashboardView from "@/views/DashboardView.vue";
import DevicesPanel from "@/components/DevicesPanel.vue";
import RemotePanel from "@/components/RemotePanel.vue";
import FilesPanel from "@/components/FilesPanel.vue";
import UpdatesPanel from "@/components/UpdatesPanel.vue";
import ScheduledTaskPanel from "@/components/ScheduledTaskPanel.vue";
import AlertCenterPanel from "@/components/AlertCenterPanel.vue";
import DiagnosticsView from "@/views/DiagnosticsView.vue";
import SystemSettingsPanel from "@/components/SystemSettingsPanel.vue";
import LogsPanel from "@/components/LogsPanel.vue";
import GroupsPanel from "@/components/GroupsPanel.vue";
import UserManagementPanel from "@/components/UserManagementPanel.vue";

export const SECTION_ROUTES: RouteRecordRaw[] = [
  { path: "/dashboard", name: "dashboard", component: DashboardView, meta: { requiresAuth: true, label: "仪表盘" } },
  { path: "/devices", name: "devices", component: DevicesPanel, meta: { requiresAuth: true, label: "设备管理" } },
  { path: "/remote", name: "remote", component: RemotePanel, meta: { requiresAuth: true, label: "远程连接" } },
  { path: "/files", name: "files", component: FilesPanel, meta: { requiresAuth: true, label: "文件管理" } },
  { path: "/updates", name: "updates", component: UpdatesPanel, meta: { requiresAuth: true, label: "批量更新" } },
  { path: "/scheduled", name: "scheduled", component: ScheduledTaskPanel, meta: { requiresAuth: true, label: "定时任务" } },
  { path: "/alerts", name: "alerts", component: AlertCenterPanel, meta: { requiresAuth: true, label: "告警中心" } },
  { path: "/diagnostics", name: "diagnostics", component: DiagnosticsView, meta: { requiresAuth: true, label: "系统诊断" } },
  {
    path: "/settings",
    name: "settings",
    component: SystemSettingsPanel,
    meta: { requiresAuth: true, adminOnly: true, label: "系统设置" },
  },
  { path: "/logs", name: "logs", component: LogsPanel, meta: { requiresAuth: true, label: "操作日志" } },
  { path: "/groups", name: "groups", component: GroupsPanel, meta: { requiresAuth: true, label: "分组管理" } },
  {
    path: "/users",
    name: "users",
    component: UserManagementPanel,
    meta: { requiresAuth: true, adminOnly: true, label: "用户管理" },
  },
];

export const APP_ROUTES: RouteRecordRaw[] = [
  { path: "/", redirect: "/dashboard" },
  ...SECTION_ROUTES,
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];
