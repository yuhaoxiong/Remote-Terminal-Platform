import type { RouteRecordRaw } from "vue-router";

type SectionRouteDefinition = {
  path: string;
  name: string;
  meta: NonNullable<RouteRecordRaw["meta"]>;
};

export const SECTION_ROUTE_DEFINITIONS: SectionRouteDefinition[] = [
  { path: "/dashboard", name: "dashboard", meta: { requiresAuth: true, label: "仪表盘" } },
  { path: "/devices", name: "devices", meta: { requiresAuth: true, label: "设备管理" } },
  { path: "/remote", name: "remote", meta: { requiresAuth: true, label: "远程连接" } },
  { path: "/files", name: "files", meta: { requiresAuth: true, label: "文件管理" } },
  { path: "/updates", name: "updates", meta: { requiresAuth: true, label: "批量更新" } },
  { path: "/scheduled", name: "scheduled", meta: { requiresAuth: true, label: "定时任务" } },
  { path: "/alerts", name: "alerts", meta: { requiresAuth: true, label: "告警中心" } },
  { path: "/diagnostics", name: "diagnostics", meta: { requiresAuth: true, label: "系统诊断" } },
  {
    path: "/settings",
    name: "settings",
    meta: { requiresAuth: true, adminOnly: true, label: "系统设置" },
  },
  { path: "/logs", name: "logs", meta: { requiresAuth: true, label: "操作日志" } },
  { path: "/groups", name: "groups", meta: { requiresAuth: true, label: "分组管理" } },
  {
    path: "/users",
    name: "users",
    meta: { requiresAuth: true, adminOnly: true, label: "用户管理" },
  },
];

const routeComponents: Record<string, NonNullable<RouteRecordRaw["component"]>> = {
  dashboard: () => import("@/views/DashboardView.vue"),
  devices: () => import("@/views/DevicesView.vue"),
  remote: () => import("@/views/RemoteView.vue"),
  files: () => import("@/views/FilesView.vue"),
  updates: () => import("@/views/UpdatesView.vue"),
  scheduled: () => import("@/views/ScheduledView.vue"),
  alerts: () => import("@/views/AlertsView.vue"),
  diagnostics: () => import("@/views/DiagnosticsView.vue"),
  settings: () => import("@/views/SettingsView.vue"),
  logs: () => import("@/views/LogsView.vue"),
  groups: () => import("@/views/GroupsView.vue"),
  users: () => import("@/views/UsersView.vue"),
};

export const SECTION_ROUTES: RouteRecordRaw[] = SECTION_ROUTE_DEFINITIONS.map((route): RouteRecordRaw => ({
  ...route,
  component: routeComponents[route.name],
}));

export const APP_ROUTES: RouteRecordRaw[] = [
  { path: "/", redirect: "/dashboard" },
  ...SECTION_ROUTES,
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];
