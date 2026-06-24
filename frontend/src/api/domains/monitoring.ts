import { api } from "../core";

export interface MonitoringOverviewResponse {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  unknown_devices: number;
}

export interface DeviceMetricRead {
  id: number;
  device_id: number;
  status: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  recorded_at: string;
}

export interface DeviceMetricListResponse {
  total: number;
  items: DeviceMetricRead[];
}

export async function getMonitoringOverview(): Promise<MonitoringOverviewResponse> {
  const response = await api.get<MonitoringOverviewResponse>("/monitoring/overview");
  return response.data;
}

export async function listDeviceMetrics(deviceId: number, limit = 20): Promise<DeviceMetricListResponse> {
  const response = await api.get<DeviceMetricListResponse>(`/devices/${deviceId}/metrics`, { params: { limit } });
  return response.data;
}
