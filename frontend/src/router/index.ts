import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/dashboard", name: "dashboard", component: () => import("@/components/DashboardPanel.vue") },
    { path: "/devices", name: "devices", component: () => import("@/components/DevicesPanel.vue") },
    { path: "/remote", name: "remote", component: () => import("@/components/RemotePanel.vue") },
    { path: "/files", name: "files", component: () => import("@/components/FilesPanel.vue") },
    { path: "/updates", name: "updates", component: () => import("@/components/UpdatesPanel.vue") },
    { path: "/scheduled", name: "scheduled", component: () => import("@/components/ScheduledTaskPanel.vue") },
    { path: "/alerts", name: "alerts", component: () => import("@/components/AlertCenterPanel.vue") },
    { path: "/diagnostics", name: "diagnostics", component: () => import("@/components/DiagnosticsPanel.vue") },
    { path: "/settings", name: "settings", component: () => import("@/components/SystemSettingsPanel.vue") },
    { path: "/logs", name: "logs", component: () => import("@/components/LogsPanel.vue") },
    { path: "/groups", name: "groups", component: () => import("@/components/GroupsPanel.vue") },
    { path: "/users", name: "users", component: () => import("@/components/UserManagementPanel.vue") },
  ],
});

export default router;
