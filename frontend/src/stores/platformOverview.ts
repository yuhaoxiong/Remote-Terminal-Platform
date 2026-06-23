import { ref } from "vue";
import { defineStore } from "pinia";

import { fetchHealth } from "../api/health";
import {
  getAlertSummary,
  getDiagnosticsConfig,
  getMonitoringOverview,
  type AlertSummaryResponse,
  type DiagnosticsConfigResponse,
  type MonitoringOverviewResponse,
} from "../api/platform";
import { useLogsStore } from "./logs";

export const usePlatformOverviewStore = defineStore("platformOverview", () => {
  const serverOverview = ref<MonitoringOverviewResponse | null>(null);
  const alertSummary = ref<AlertSummaryResponse | null>(null);
  const diagnosticsConfig = ref<DiagnosticsConfigResponse | null>(null);
  const diagnosticsLoading = ref(false);
  const backendHealthStatus = ref<"checking" | "healthy" | "failed">("checking");
  const backendHealthDetail = ref("检测中");
  const metricLoadWarning = ref("");

  function setOverview(
    overview: MonitoringOverviewResponse | null,
    summary: AlertSummaryResponse | null,
  ) {
    serverOverview.value = overview;
    alertSummary.value = summary;
  }

  function setMetricLoadWarning(message: string) {
    metricLoadWarning.value = message;
  }

  async function refreshOverview() {
    const [overviewResponse, alertSummaryResponse] = await Promise.all([
      getMonitoringOverview(),
      getAlertSummary(),
    ]);
    setOverview(overviewResponse, alertSummaryResponse);
  }

  async function loadDiagnosticsConfig() {
    const logsStore = useLogsStore();
    diagnosticsLoading.value = true;
    try {
      diagnosticsConfig.value = await getDiagnosticsConfig();
    } catch {
      logsStore.prependLocalLog("加载诊断配置", "系统", "blocked", "无法读取诊断配置，请检查后端服务。");
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

  function reset() {
    serverOverview.value = null;
    alertSummary.value = null;
    diagnosticsConfig.value = null;
    diagnosticsLoading.value = false;
    backendHealthStatus.value = "checking";
    backendHealthDetail.value = "检测中";
    metricLoadWarning.value = "";
  }

  return {
    serverOverview,
    alertSummary,
    diagnosticsConfig,
    diagnosticsLoading,
    backendHealthStatus,
    backendHealthDetail,
    metricLoadWarning,
    setOverview,
    setMetricLoadWarning,
    refreshOverview,
    loadDiagnosticsConfig,
    loadBackendHealth,
    reset,
  };
});
