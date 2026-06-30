import { api } from "../core";

export interface RemoteSessionResponse {
  device_id: number;
  session_type: "ssh" | "vnc";
  status: string;
  remote_port: number;
  websocket_url: string | null;
  proxy_url: string | null;
  vnc_password?: string | null;
}

export interface SyncConfigResponse {
  device_id: number;
  status: string;
  config: string;
}

export async function openSshSession(deviceId: number): Promise<RemoteSessionResponse> {
  const response = await api.post<RemoteSessionResponse>(`/devices/${deviceId}/remote/ssh`);
  return response.data;
}

export async function openVncSession(deviceId: number): Promise<RemoteSessionResponse> {
  const response = await api.post<RemoteSessionResponse>(`/devices/${deviceId}/remote/vnc`);
  return response.data;
}

export async function syncDeviceConfig(deviceId: number): Promise<SyncConfigResponse> {
  const response = await api.post<SyncConfigResponse>(`/devices/${deviceId}/sync-config`);
  return response.data;
}
