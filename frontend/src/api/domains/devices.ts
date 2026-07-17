import { api } from "../core";

export interface DeviceRead {
  id: number;
  device_uuid: string;
  name: string;
  device_sn: string;
  project_id: number | null;
  expected_profile_id: number | null;
  actual_profile_id: number | null;
  device_role: string | null;
  is_test_device: boolean;
  location: string | null;
  hardware_model: string | null;
  ssh_port: number | null;
  vnc_port: number | null;
  ssh_user: string;
  ssh_auth_type: string;
  ssh_credential_configured: boolean;
  local_ip: string | null;
  os_version: string | null;
  description: string | null;
  tags: string[] | null;
  group_id: number | null;
  status: string;
  last_seen: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceListResponse {
  total: number;
  items: DeviceRead[];
}

export interface DeviceCreateRequest {
  name: string;
  device_sn: string;
  project_id?: number | null;
  expected_profile_id?: number | null;
  device_role?: string | null;
  is_test_device?: boolean;
  group_id?: number | null;
  location?: string;
  tags?: string[];
  ssh_user?: string;
  ssh_auth_type?: string;
  ssh_password?: string;
  ssh_port?: number | null;
  vnc_port?: number | null;
}

export type DeviceUpdateRequest = Partial<Omit<DeviceCreateRequest, "device_sn">> & {
  status?: string;
};

export interface DeviceStatusResponse {
  id: number;
  status: string;
  last_seen: string | null;
}

export async function listDevices(): Promise<DeviceListResponse> {
  const response = await api.get<DeviceListResponse>("/devices");
  return response.data;
}

export async function createDevice(payload: DeviceCreateRequest): Promise<DeviceRead> {
  const response = await api.post<DeviceRead>("/devices", payload);
  return response.data;
}

export async function updateDevice(deviceId: number, payload: DeviceUpdateRequest): Promise<DeviceRead> {
  const response = await api.put<DeviceRead>(`/devices/${deviceId}`, payload);
  return response.data;
}

export async function deleteDevice(deviceId: number): Promise<void> {
  await api.delete(`/devices/${deviceId}`);
}

export async function getDeviceStatus(deviceId: number): Promise<DeviceStatusResponse> {
  const response = await api.get<DeviceStatusResponse>(`/devices/${deviceId}/status`);
  return response.data;
}
