import { api } from "../core";

export interface DeviceFileItem {
  name: string;
  path: string;
  type: "file" | "directory" | string;
  size: number;
  modified_at: string | null;
}

export interface DeviceFileListResponse {
  device_id: number;
  path: string;
  items: DeviceFileItem[];
}

export interface DeviceFileOperationResponse {
  device_id: number;
  remote_path: string;
  status: string;
  size: number | null;
}

export async function listDeviceFiles(deviceId: number, path = "/"): Promise<DeviceFileListResponse> {
  const response = await api.get<DeviceFileListResponse>(`/devices/${deviceId}/files`, { params: { path } });
  return response.data;
}

export async function uploadDeviceFile(deviceId: number, remotePath: string, file: File): Promise<DeviceFileOperationResponse> {
  const form = new FormData();
  form.append("remote_path", remotePath);
  form.append("file", file);
  const response = await api.post<DeviceFileOperationResponse>(`/devices/${deviceId}/files/upload`, form);
  return response.data;
}

export async function downloadDeviceFile(deviceId: number, remotePath: string): Promise<Blob> {
  const response = await api.get<Blob>(`/devices/${deviceId}/files/download`, {
    params: { remote_path: remotePath },
    responseType: "blob",
  });
  return response.data;
}

export async function deleteDeviceFile(deviceId: number, remotePath: string): Promise<DeviceFileOperationResponse> {
  const response = await api.delete<DeviceFileOperationResponse>(`/devices/${deviceId}/files`, { data: { remote_path: remotePath } });
  return response.data;
}
