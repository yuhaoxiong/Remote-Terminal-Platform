import { computed, ref } from "vue";
import { defineStore } from "pinia";

export type DeviceStatus = "online" | "offline" | "degraded" | "unknown";

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

  return { devices, monitoringAvailability };
});
