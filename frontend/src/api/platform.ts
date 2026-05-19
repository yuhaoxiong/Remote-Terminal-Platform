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

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
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
  group_id?: number | null;
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

export interface GroupCreateRequest {
  name: string;
  parent_id?: number | null;
  description?: string;
}

export type GroupUpdateRequest = Partial<GroupCreateRequest>;

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

export interface ListLogsParams {
  offset?: number;
  limit?: number;
  action?: string;
  target_type?: string;
  status?: string;
}

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

export interface ScheduledTaskRead {
  id: number;
  name: string;
  task_type: string;
  schedule: string;
  command: string | null;
  target_filter: Record<string, unknown> | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskListResponse {
  total: number;
  items: ScheduledTaskRead[];
}

export interface ScheduledTaskCreateRequest {
  name: string;
  task_type: string;
  schedule: string;
  command?: string | null;
  target_filter?: Record<string, unknown> | null;
  enabled?: boolean;
}

export type ScheduledTaskUpdateRequest = Partial<ScheduledTaskCreateRequest>;

export interface ScheduledTaskExecuteResponse {
  task_id: number;
  status: string;
  output_summary: string;
}

export interface RemoteSessionResponse {
  device_id: number;
  session_type: "ssh" | "vnc";
  status: string;
  remote_port: number;
  websocket_url: string | null;
  proxy_url: string | null;
}

export interface SyncConfigResponse {
  device_id: number;
  status: string;
  config: string;
}

export interface DiagnosticsSecuritySummary {
  credential_encryption_configured: boolean;
  jwt_secret_configured: boolean;
  default_admin_password_in_use: boolean;
  default_device_ssh_password_in_use: boolean;
  warnings: string[];
}

export interface DiagnosticsConfigResponse {
  service_name: string;
  version: string;
  api_prefix: string;
  database: string;
  file_backend: string;
  remote_gateway_host: string;
  vnc_gateway_host: string;
  ssh_timeout_seconds: number;
  vnc_timeout_seconds: number;
  default_device_ssh_user: string;
  security: DiagnosticsSecuritySummary;
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

export async function changePassword(payload: PasswordChangeRequest): Promise<void> {
  await api.put("/auth/password", payload);
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

export async function createGroup(payload: GroupCreateRequest): Promise<GroupRead> {
  const response = await api.post<GroupRead>("/groups", payload);
  return response.data;
}

export async function updateGroup(groupId: number, payload: GroupUpdateRequest): Promise<GroupRead> {
  const response = await api.put<GroupRead>(`/groups/${groupId}`, payload);
  return response.data;
}

export async function deleteGroup(groupId: number): Promise<void> {
  await api.delete(`/groups/${groupId}`);
}

export async function listLogs(params?: ListLogsParams): Promise<OperationLogListResponse> {
  const response = await api.get<OperationLogListResponse>("/logs", { params });
  return response.data;
}

export async function exportLogs(params?: Omit<ListLogsParams, "offset" | "limit">): Promise<Blob> {
  const response = await api.get<Blob>("/logs/export", { params, responseType: "blob" });
  return response.data;
}

export async function getMonitoringOverview(): Promise<MonitoringOverviewResponse> {
  const response = await api.get<MonitoringOverviewResponse>("/monitoring/overview");
  return response.data;
}

export async function listDeviceMetrics(deviceId: number, limit = 20): Promise<DeviceMetricListResponse> {
  const response = await api.get<DeviceMetricListResponse>(`/devices/${deviceId}/metrics`, { params: { limit } });
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

export async function listScheduledTasks(): Promise<ScheduledTaskListResponse> {
  const response = await api.get<ScheduledTaskListResponse>("/scheduled-tasks");
  return response.data;
}

export async function createScheduledTask(payload: ScheduledTaskCreateRequest): Promise<ScheduledTaskRead> {
  const response = await api.post<ScheduledTaskRead>("/scheduled-tasks", payload);
  return response.data;
}

export async function updateScheduledTask(taskId: number, payload: ScheduledTaskUpdateRequest): Promise<ScheduledTaskRead> {
  const response = await api.put<ScheduledTaskRead>(`/scheduled-tasks/${taskId}`, payload);
  return response.data;
}

export async function deleteScheduledTask(taskId: number): Promise<void> {
  await api.delete(`/scheduled-tasks/${taskId}`);
}

export async function toggleScheduledTask(taskId: number): Promise<ScheduledTaskRead> {
  const response = await api.post<ScheduledTaskRead>(`/scheduled-tasks/${taskId}/toggle`);
  return response.data;
}

export async function executeScheduledTask(taskId: number): Promise<ScheduledTaskExecuteResponse> {
  const response = await api.post<ScheduledTaskExecuteResponse>(`/scheduled-tasks/${taskId}/execute`);
  return response.data;
}

export async function listScheduledTaskLogs(taskId: number): Promise<OperationLogListResponse> {
  const response = await api.get<OperationLogListResponse>(`/scheduled-tasks/${taskId}/logs`);
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

export async function syncDeviceConfig(deviceId: number): Promise<SyncConfigResponse> {
  const response = await api.post<SyncConfigResponse>(`/devices/${deviceId}/sync-config`);
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

export async function getDiagnosticsConfig(): Promise<DiagnosticsConfigResponse> {
  const response = await api.get<DiagnosticsConfigResponse>("/diagnostics/config");
  return response.data;
}

export function buildApiWebSocketUrl(path: string, token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const separator = path.includes("?") ? "&" : "?";
  return `${protocol}//${window.location.host}${path}${separator}token=${encodeURIComponent(token)}`;
}
