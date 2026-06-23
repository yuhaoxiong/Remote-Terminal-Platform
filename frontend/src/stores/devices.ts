import { computed, ref } from "vue";
import { defineStore } from "pinia";

import {
  buildApiWebSocketUrl,
  getAccessToken,
  type DeviceRead,
  type UpdateTaskDeviceRead,
} from "../api/platform";

export type DeviceStatus = "online" | "offline" | "degraded" | "unknown";

/**
 * 将后端返回的状态字符串标准化为 DeviceStatus。
 */
export function normalizeDeviceStatus(status: string): DeviceStatus {
  if (status === "online" || status === "offline" || status === "degraded") {
    return status;
  }
  return "unknown";
}

/**
 * 设备视图模型。承载列表展示与监控所需的全部字段(含最新指标快照),
 * 由 App.vue 的 mapDevice / attachLatestMetrics 负责装配。
 */
export interface Device {
  id: number;
  name: string;
  device_sn: string;
  project_id: string;
  group: string;
  group_id: number | null;
  location: string;
  tags: string[];
  status: DeviceStatus;
  ssh_port: number | null;
  vnc_port: number | null;
  ssh_user: string;
  ssh_auth_type: string;
  ssh_credential_configured: boolean;
  cpu: number | null;
  memory: number | null;
  disk: number | null;
  metricRecordedAt: string | null;
  metricStale: boolean;
  metricLoadFailed: boolean;
}

/**
 * 设备 store。
 * 作为设备列表的单一数据源(此前散落在 App.vue 的多处读写),
 * 并提供纯依赖列表的派生指标 monitoringAvailability(监控覆盖率)。
 * 设备的加载/映射/WebSocket 增量等装配逻辑暂仍由调用方(App.vue)负责。
 */
export const useDevicesStore = defineStore("devices", () => {
  const devices = ref<Device[]>([]);
  const deviceSearch = ref("");
  const selectedGroupId = ref<number | null>(null);
  const deviceStatusFilter = ref<DeviceStatus | "">("");
  const deviceProjectFilter = ref("");
  const deviceTagFilter = ref("");
  const filePanelDevice = ref<Device | null>(null);

  const monitoringAvailability = computed(() => {
    const withMetrics = devices.value.filter((device) => device.metricRecordedAt && !device.metricLoadFailed).length;
    const latestRecordedAt =
      devices.value
        .map((device) => device.metricRecordedAt)
        .filter((value): value is string => Boolean(value))
        .sort((left, right) => new Date(right).getTime() - new Date(left).getTime())[0] ?? null;
    return {
      withMetrics,
      withoutMetrics: Math.max(devices.value.length - withMetrics, 0),
      latestRecordedAt,
    };
  });

  // 设备列表的综合筛选(关键字 / 分组 / 状态 / 项目 / 标签),设备区与文件区共享同一视图
  const visibleDevices = computed(() => {
    const keyword = deviceSearch.value.trim().toLowerCase();
    const projectKeyword = deviceProjectFilter.value.trim().toLowerCase();
    const tagKeyword = deviceTagFilter.value.trim().toLowerCase();
    return devices.value.filter((device) => {
      const matchesGroup = selectedGroupId.value === null || device.group_id === selectedGroupId.value;
      const matchesStatus = !deviceStatusFilter.value || device.status === deviceStatusFilter.value;
      const matchesProject = !projectKeyword || device.project_id.toLowerCase().includes(projectKeyword);
      const matchesTag = !tagKeyword || device.tags.some((tag) => tag.toLowerCase().includes(tagKeyword));
      const matchesKeyword =
        !keyword ||
        [device.name, device.device_sn, device.project_id, device.group, device.tags.join(",")]
          .join(" ")
          .toLowerCase()
          .includes(keyword);
      return matchesGroup && matchesStatus && matchesProject && matchesTag && matchesKeyword;
    });
  });

  // 文件管理当前选中的设备(设备区内联面板与文件区共享)
  function openFilePanel(device: Device) {
    filePanelDevice.value = device;
  }

  return {
    devices,
    deviceSearch,
    selectedGroupId,
    deviceStatusFilter,
    deviceProjectFilter,
    deviceTagFilter,
    filePanelDevice,
    monitoringAvailability,
    visibleDevices,
    openFilePanel,
  };
});
