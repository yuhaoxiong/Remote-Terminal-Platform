import DashboardPanel from "@/components/DashboardPanel.vue";
import DevicesPanel from "@/components/DevicesPanel.vue";
import RemotePanel from "@/components/RemotePanel.vue";
import FilesPanel from "@/components/FilesPanel.vue";
import UpdatesPanel from "@/components/UpdatesPanel.vue";
import ScheduledTaskPanel from "@/components/ScheduledTaskPanel.vue";
import AlertCenterPanel from "@/components/AlertCenterPanel.vue";
import DiagnosticsPanel from "@/components/DiagnosticsPanel.vue";
import SystemSettingsPanel from "@/components/SystemSettingsPanel.vue";
import LogsPanel from "@/components/LogsPanel.vue";
import GroupsPanel from "@/components/GroupsPanel.vue";
import UserManagementPanel from "@/components/UserManagementPanel.vue";

// 测试路由配置 — 与 prod 路由相同,使用 @/ 别名导入 (vitest 配置了别名解析)
// mountApp() 中使用 createMemoryHistory 来保证 jsdom 兼容性
export const TEST_ROUTES = [
  { path: "/", redirect: "/dashboard" },
  { path: "/dashboard", name: "dashboard", component: DashboardPanel },
  { path: "/devices", name: "devices", component: DevicesPanel },
  { path: "/remote", name: "remote", component: RemotePanel },
  { path: "/files", name: "files", component: FilesPanel },
  { path: "/updates", name: "updates", component: UpdatesPanel },
  { path: "/scheduled", name: "scheduled", component: ScheduledTaskPanel },
  { path: "/alerts", name: "alerts", component: AlertCenterPanel },
  { path: "/diagnostics", name: "diagnostics", component: DiagnosticsPanel },
  { path: "/settings", name: "settings", component: SystemSettingsPanel },
  { path: "/logs", name: "logs", component: LogsPanel },
  { path: "/groups", name: "groups", component: GroupsPanel },
  { path: "/users", name: "users", component: UserManagementPanel },
];
