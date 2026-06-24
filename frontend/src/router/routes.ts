import type { RouteRecordRaw } from "vue-router";

import DashboardView from "@/views/DashboardView.vue";
import DevicesView from "@/views/DevicesView.vue";
import RemoteView from "@/views/RemoteView.vue";
import FilesView from "@/views/FilesView.vue";
import UpdatesView from "@/views/UpdatesView.vue";
import ScheduledView from "@/views/ScheduledView.vue";
import AlertsView from "@/views/AlertsView.vue";
import DiagnosticsView from "@/views/DiagnosticsView.vue";
import SettingsView from "@/views/SettingsView.vue";
import LogsView from "@/views/LogsView.vue";
import GroupsView from "@/views/GroupsView.vue";
import UsersView from "@/views/UsersView.vue";

export const SECTION_ROUTES: RouteRecordRaw[] = [
  { path: "/dashboard", name: "dashboard", component: DashboardView, meta: { requiresAuth: true, label: "仪表盘" } },
  { path: "/devices", name: "devices", component: DevicesView, meta: { requiresAuth: true, label: "设备管理" } },
  { path: "/remote", name: "remote", component: RemoteView, meta: { requiresAuth: true, label: "远程连接" } },
  { path: "/files", name: "files", component: FilesView, meta: { requiresAuth: true, label: "文件管理" } },
  { path: "/updates", name: "updates", component: UpdatesView, meta: { requiresAuth: true, label: "批量更新" } },
  { path: "/scheduled", name: "scheduled", component: ScheduledView, meta: { requiresAuth: true, label: "定时任务" } },
  { path: "/alerts", name: "alerts", component: AlertsView, meta: { requiresAuth: true, label: "告警中心" } },
  { path: "/diagnostics", name: "diagnostics", component: DiagnosticsView, meta: { requiresAuth: true, label: "系统诊断" } },
  {
    path: "/settings",
    name: "settings",
    component: SettingsView,
    meta: { requiresAuth: true, adminOnly: true, label: "系统设置" },
  },
  { path: "/logs", name: "logs", component: LogsView, meta: { requiresAuth: true, label: "操作日志" } },
  { path: "/groups", name: "groups", component: GroupsView, meta: { requiresAuth: true, label: "分组管理" } },
  {
    path: "/users",
    name: "users",
    component: UsersView,
    meta: { requiresAuth: true, adminOnly: true, label: "用户管理" },
  },
];

export const APP_ROUTES: RouteRecordRaw[] = [
  { path: "/", redirect: "/dashboard" },
  ...SECTION_ROUTES,
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];
