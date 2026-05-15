import axios from "axios";

const ACCESS_TOKEN_KEY = "edge-platform-access-token";
const REFRESH_TOKEN_KEY = "edge-platform-refresh-token";

const api = axios.create({
  baseURL: "/api",
});

api.interceptors.request.use((config) => {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DeviceRead {
  id: number;
  name: string;
  device_sn: string;
  project_id: string;
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
  project_id: string;
  location?: string;
  tags?: string[];
  ssh_user?: string;
  ssh_auth_type?: string;
  ssh_password?: string;
}

export type DeviceUpdateRequest = Partial<Omit<DeviceCreateRequest, "device_sn">> & {
  status?: string;
};

export interface DeviceStatusResponse {
  id: number;
  status: string;
  last_seen: string | null;
}

export interface GroupRead {
  id: number;
  name: string;
  parent_id: number | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface GroupListResponse {
  total: number;
  items: GroupRead[];
}

export interface OperationLogRead {
  id: number;
  user_id: number | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  status: string;
  detail: string | null;
  created_at: string;
}

export interface OperationLogListResponse {
  total: number;
  items: OperationLogRead[];
}

export interface MonitoringOverviewResponse {
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  unknown_devices: number;
}

export interface UpdateTaskDeviceRead {
  id: number;
  task_id: number;
  device_id: number;
  status: string;
  output_summary: string | null;
  exit_code: number | null;
  stdout_summary: string | null;
  stderr_summary: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface UpdateTaskRead {
  id: number;
  name: string;
  task_type: string;
  command: string;
  rollback_command: string | null;
  target_filter: Record<string, unknown> | null;
  execution_mode: "dry_run" | "ssh_command";
  failure_strategy: string;
  concurrency_limit: number;
  status: string;
  created_at: string;
  updated_at: string;
  device_count: number;
  devices: UpdateTaskDeviceRead[];
}

export interface UpdateTaskListResponse {
  total: number;
  items: UpdateTaskRead[];
}

export interface UpdateTaskCreateRequest {
  name: string;
  task_type: string;
  command: string;
  target_filter?: Record<string, unknown>;
  execution_mode: "dry_run" | "ssh_command";
  failure_strategy: "continue" | "pause" | "rollback";
  concurrency_limit: number;
}

export interface RemoteSessionResponse {
  device_id: number;
  session_type: "ssh" | "vnc";
  status: string;
  remote_port: number;
  websocket_url: string | null;
  proxy_url: string | null;
}

export interface FrpsImportRequest {
  dashboard_url: string;
  username: string;
  password: string;
  ssh_port_start: number;
  ssh_port_end: number;
  vnc_port_start: number;
  vnc_port_end: number;
  project_id: string;
  location?: string;
  overwrite_project_location?: boolean;
}

export interface FrpsDiscoveredDevice {
  name: string;
  device_sn: string;
  project_id: string;
  ssh_port: number;
  vnc_port: number | null;
  ssh_proxy_name: string;
  vnc_proxy_name: string | null;
  status: string;
  import_status: string;
  detail: string | null;
  existing_device_id: number | null;
}

export interface FrpsImportResponse {
  total: number;
  created: number;
  skipped: number;
  synced: number;
  conflicts: number;
  items: FrpsDiscoveredDevice[];
}

export function hasStoredAccessToken(): boolean {
  return Boolean(window.localStorage.getItem(ACCESS_TOKEN_KEY));
}

export function getAccessToken(): string | null {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAuthTokens(accessToken: string, refreshToken: string) {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearAuthTokens() {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export async function loginAdmin(username: string, password: string): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", { username, password });
  return response.data;
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

export async function listGroups(): Promise<GroupListResponse> {
  const response = await api.get<GroupListResponse>("/groups");
  return response.data;
}

export async function listLogs(): Promise<OperationLogListResponse> {
  const response = await api.get<OperationLogListResponse>("/logs");
  return response.data;
}

export async function getMonitoringOverview(): Promise<MonitoringOverviewResponse> {
  const response = await api.get<MonitoringOverviewResponse>("/monitoring/overview");
  return response.data;
}

export async function listUpdateTasks(): Promise<UpdateTaskListResponse> {
  const response = await api.get<UpdateTaskListResponse>("/update-tasks");
  return response.data;
}

export async function createUpdateTask(payload: UpdateTaskCreateRequest): Promise<UpdateTaskRead> {
  const response = await api.post<UpdateTaskRead>("/update-tasks", payload);
  return response.data;
}

export async function executeUpdateTask(taskId: number): Promise<UpdateTaskRead> {
  const response = await api.post<UpdateTaskRead>(`/update-tasks/${taskId}/execute`);
  return response.data;
}

export async function cancelUpdateTask(taskId: number): Promise<UpdateTaskRead> {
  const response = await api.post<UpdateTaskRead>(`/update-tasks/${taskId}/cancel`);
  return response.data;
}

export async function openSshSession(deviceId: number): Promise<RemoteSessionResponse> {
  const response = await api.post<RemoteSessionResponse>(`/devices/${deviceId}/remote/ssh`);
  return response.data;
}

export async function openVncSession(deviceId: number): Promise<RemoteSessionResponse> {
  const response = await api.post<RemoteSessionResponse>(`/devices/${deviceId}/remote/vnc`);
  return response.data;
}

export async function discoverFrpsDevices(payload: FrpsImportRequest): Promise<FrpsImportResponse> {
  const response = await api.post<FrpsImportResponse>("/frps/discover", payload);
  return response.data;
}

export async function importFrpsDevices(payload: FrpsImportRequest): Promise<FrpsImportResponse> {
  const response = await api.post<FrpsImportResponse>("/frps/import", payload);
  return response.data;
}

export function buildApiWebSocketUrl(path: string, token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const separator = path.includes("?") ? "&" : "?";
  return `${protocol}//${window.location.host}${path}${separator}token=${encodeURIComponent(token)}`;
}
