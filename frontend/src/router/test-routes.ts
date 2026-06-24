import type { RouteRecordRaw } from "vue-router";

import AlertsView from "@/views/AlertsView.vue";
import DashboardView from "@/views/DashboardView.vue";
import DevicesView from "@/views/DevicesView.vue";
import DiagnosticsView from "@/views/DiagnosticsView.vue";
import FilesView from "@/views/FilesView.vue";
import GroupsView from "@/views/GroupsView.vue";
import LogsView from "@/views/LogsView.vue";
import RemoteView from "@/views/RemoteView.vue";
import ScheduledView from "@/views/ScheduledView.vue";
import SettingsView from "@/views/SettingsView.vue";
import UpdatesView from "@/views/UpdatesView.vue";
import UsersView from "@/views/UsersView.vue";
import { SECTION_ROUTE_DEFINITIONS } from "./routes";

const testRouteComponents: Record<string, NonNullable<RouteRecordRaw["component"]>> = {
  dashboard: DashboardView,
  devices: DevicesView,
  remote: RemoteView,
  files: FilesView,
  updates: UpdatesView,
  scheduled: ScheduledView,
  alerts: AlertsView,
  diagnostics: DiagnosticsView,
  settings: SettingsView,
  logs: LogsView,
  groups: GroupsView,
  users: UsersView,
};

const sectionTestRoutes: RouteRecordRaw[] = SECTION_ROUTE_DEFINITIONS.map((route): RouteRecordRaw => ({
  ...route,
  component: testRouteComponents[route.name],
}));

// 测试路由配置与生产路由共享 route meta，但保留同步组件以减少 jsdom 下的异步渲染噪声。
export const TEST_ROUTES: RouteRecordRaw[] = [
  { path: "/", redirect: "/dashboard" },
  ...sectionTestRoutes,
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];
