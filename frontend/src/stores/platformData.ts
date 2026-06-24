import { ref } from "vue";
import { defineStore } from "pinia";

import {
  clearAuthTokens,
  getCurrentUser,
  listDevices,
  listDeviceMetrics,
  listGroups,
  listUpdateTasks,
  type DeviceMetricRead,
} from "../api/platform";
import { useAuthStore } from "./auth";
import { mapDevice, normalizeDeviceStatus, type Device } from "./devices";
import { mapGroup } from "./groups";
import { useDevicesStore } from "./devices";
import { useGroupsStore } from "./groups";
import { useLogsStore } from "./logs";
import { usePlatformOverviewStore } from "./platformOverview";
import { mapUpdateTask, useUpdatesStore } from "./updates";

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

export const usePlatformDataStore = defineStore("platformData", () => {
  const loading = ref(false);
  const operationError = ref("");

  function setOperationError(message: string) {
    operationError.value = message;
  }

  function clearOperationError() {
    operationError.value = "";
  }

  async function attachLatestMetrics(sourceDevices: Device[]): Promise<Device[]> {
    const platformOverviewStore = usePlatformOverviewStore();
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
    platformOverviewStore.setMetricLoadWarning(failedCount > 0 ? `有 ${failedCount} 台设备指标加载失败` : "");
    return enriched;
  }

  async function loadPlatformData() {
    const authStore = useAuthStore();
    const devicesStore = useDevicesStore();
    const groupsStore = useGroupsStore();
    const platformOverviewStore = usePlatformOverviewStore();
    const updatesStore = useUpdatesStore();

    loading.value = true;
    operationError.value = "";
    try {
      const [userResponse, groupResponse, deviceResponse, updateResponse] = await Promise.all([
        getCurrentUser(),
        listGroups(),
        listDevices(),
        listUpdateTasks(),
        platformOverviewStore.refreshOverview(),
      ]);
      authStore.currentUser = userResponse;
      const mappedGroups = groupResponse.items.map((group) => mapGroup(group, []));
      const mappedDevices = deviceResponse.items.map((device) => mapDevice(device, mappedGroups));
      devicesStore.devices = await attachLatestMetrics(mappedDevices);
      groupsStore.groups = groupResponse.items.map((group) => mapGroup(group, devicesStore.devices));
      updatesStore.updateTasks = updateResponse.items.map(mapUpdateTask);
    } catch (error) {
      if (isAuthFailure(error)) {
        operationError.value = "登录状态已过期，请重新登录。";
        clearAuthTokens();
        authStore.authenticated = false;
        return;
      }
      if (isPermissionFailure(error)) {
        operationError.value = "当前账号无权限加载该数据，请联系管理员调整权限。";
        return;
      }
      operationError.value = isGatewayFailure(error)
        ? "后端服务不可达或代理配置错误，请检查 Nginx /api 反向代理和后端进程。"
        : "无法从后端加载平台数据，请确认后端服务已启动。";
    } finally {
      loading.value = false;
    }
  }

  function clearPlatformData() {
    const authStore = useAuthStore();
    const devicesStore = useDevicesStore();
    const groupsStore = useGroupsStore();
    const logsStore = useLogsStore();
    const platformOverviewStore = usePlatformOverviewStore();
    const updatesStore = useUpdatesStore();

    authStore.currentUser = null;
    devicesStore.devices = [];
    groupsStore.groups = [];
    updatesStore.updateTasks = [];
    logsStore.auditLogs = [];
    logsStore.auditLogsTotal = 0;
    platformOverviewStore.reset();
    operationError.value = "";
  }

  return {
    loading,
    operationError,
    setOperationError,
    clearOperationError,
    loadPlatformData,
    clearPlatformData,
  };
});
