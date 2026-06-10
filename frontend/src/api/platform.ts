import axios, { AxiosHeaders, type AxiosError, type InternalAxiosRequestConfig } from "axios";

const ACCESS_TOKEN_KEY = "edge-platform-access-token";
const REFRESH_TOKEN_KEY = "edge-platform-refresh-token";
export const AUTH_EXPIRED_EVENT = "edge-platform-auth-expired";

type AuthRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
  skipAuthRefresh?: boolean;
};

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

let refreshPromise: Promise<TokenResponse> | null = null;

function getRefreshToken(): string | null {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY);
}

function isAuthEndpoint(url: string | undefined): boolean {
  return Boolean(url?.includes("/auth/login") || url?.includes("/auth/refresh"));
}

function notifyAuthExpired() {
  clearAuthTokens();
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const originalRequest = error.config as AuthRequestConfig | undefined;
    if (
      status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      originalRequest.skipAuthRefresh ||
      isAuthEndpoint(originalRequest.url)
    ) {
      throw error;
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      notifyAuthExpired();
      throw error;
    }

    originalRequest._retry = true;
    try {
      refreshPromise ??= api
        .post<TokenResponse>(
          "/auth/refresh",
          { refresh_token: refreshToken },
          { skipAuthRefresh: true } as AuthRequestConfig,
        )
        .then((response) => response.data)
        .finally(() => {
          refreshPromise = null;
        });
      const token = await refreshPromise;
      setAuthTokens(token.access_token, token.refresh_token);
      originalRequest.headers = AxiosHeaders.from(originalRequest.headers);
      originalRequest.headers.set("Authorization", `Bearer ${token.access_token}`);
      return api(originalRequest);
    } catch (refreshError) {
      notifyAuthExpired();
      throw refreshError;
    }
  },
);

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PasswordChangeRequest {
  old_password: string;
  new_password: string;
}

export type UserRole = "admin" | "operator";

export interface CurrentUserResponse {
  id: number;
  username: string;
  role: UserRole | string;
  is_active: boolean;
}

export interface UserRead {
  id: number;
  username: string;
  role: UserRole | string;
  is_active: boolean;
  last_login_at: string | null;
  last_login_ip: string | null;
  password_changed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  total: number;
  items: UserRead[];
}

export interface UserCreateRequest {
  username: string;
  password: string;
  role: UserRole;
  is_active?: boolean;
}

export interface UserUpdateRequest {
  role?: UserRole;
  is_active?: boolean;
}

export interface UserResetPasswordRequest {
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

export interface UpdateTaskTargetDeviceRead {
  id: number;
  name: string;
  device_sn: string;
  project_id: string;
  group_id: number | null;
  status: string;
  ssh_port: number | null;
  ssh_credential_configured: boolean;
  tags: string[] | null;
  location: string | null;
}

export interface UpdateTaskTargetPreviewRequest {
  target_filter?: Record<string, unknown> | null;
  execution_mode?: "dry_run" | "ssh_command";
}

export interface UpdateTaskTargetPreviewResponse {
  total: number;
  items: UpdateTaskTargetDeviceRead[];
  warnings: string[];
}

export interface UpdateTaskTemplateRead {
  id: number;
  name: string;
  description: string | null;
  command: string;
  task_type: string;
  default_execution_mode: "dry_run" | "ssh_command";
  created_at: string;
  updated_at: string;
}

export interface UpdateTaskTemplateListResponse {
  total: number;
  items: UpdateTaskTemplateRead[];
}

export interface UpdateTaskTemplateCreateRequest {
  name: string;
  description?: string | null;
  command: string;
  task_type?: string;
  default_execution_mode?: "dry_run" | "ssh_command";
}

export type UpdateTaskTemplateUpdateRequest = Partial<UpdateTaskTemplateCreateRequest>;

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
  execution_mode: string;
  failure_strategy: string;
  concurrency_limit: number;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  next_run_at: string | null;
  running: boolean;
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
  execution_mode?: string;
  failure_strategy?: string;
  concurrency_limit?: number;
}

export type ScheduledTaskUpdateRequest = Partial<ScheduledTaskCreateRequest>;

export interface ScheduledTaskExecuteResponse {
  task_id: number;
  status: string;
  output_summary: string;
  run_id: number | null;
}

export interface ScheduledTaskRunRead {
  id: number;
  scheduled_task_id: number;
  trigger_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  output_summary: string | null;
  error_message: string | null;
  created_update_task_id: number | null;
  created_at: string;
}

export interface ScheduledTaskRunListResponse {
  total: number;
  items: ScheduledTaskRunRead[];
}

export interface SchedulerStatusResponse {
  enabled: boolean;
  running: boolean;
  poll_interval_seconds: number;
  last_scan_at: string | null;
  last_error: string | null;
  job_count: number;
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

export interface DiagnosticsMigrationSummary {
  current_revision: string | null;
  head_revision: string | null;
  has_pending_migrations: boolean;
  last_error: string | null;
}

export interface DiagnosticsSshHostKeySummary {
  policy: string;
  known_hosts_configured: boolean;
  warnings: string[];
}

export interface DiagnosticsAuthLifetimeSummary {
  access_expire_minutes: number;
  refresh_expire_minutes: number;
  jwt_secret_configured: boolean;
}

export interface DiagnosticsDatabaseSummary {
  summary: string;
  sqlite_backup_recommended: boolean;
}

export interface DiagnosticsSchedulerSummary {
  enabled: boolean;
  running: boolean;
  poll_interval_seconds: number;
  last_scan_at: string | null;
  last_error: string | null;
  enabled_task_count: number;
  failed_run_count: number;
  warnings: string[];
}

export interface DiagnosticsAlertSummary {
  active_count: number;
  critical_count: number;
  latest_alert_at: string | null;
  warnings: string[];
}

export interface DiagnosticsNotificationSummary {
  enabled_channel_count: number;
  enabled_policy_count: number;
  failed_delivery_count: number;
  retrying_delivery_count: number;
  warnings: string[];
}

export interface DiagnosticsUserSummary {
  total_count: number;
  active_count: number;
  admin_count: number;
  operator_count: number;
  disabled_count: number;
  warnings: string[];
}

export interface DiagnosticsSystemSettingsSummary {
  table_available: boolean;
  database_override_count: number;
  pending_restart_count: number;
  credential_encryption_configured: boolean;
  systemd_managed: boolean;
  invalid_override_count: number;
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
  migration: DiagnosticsMigrationSummary;
  ssh_host_key: DiagnosticsSshHostKeySummary;
  auth_lifetime: DiagnosticsAuthLifetimeSummary;
  database_status: DiagnosticsDatabaseSummary;
  scheduler: DiagnosticsSchedulerSummary;
  alerts: DiagnosticsAlertSummary;
  notifications: DiagnosticsNotificationSummary;
  users: DiagnosticsUserSummary;
  system_settings: DiagnosticsSystemSettingsSummary;
}

export interface SystemSettingSchemaItem {
  key: string;
  name: string;
  description: string;
  category: string;
  value_type: "string" | "int" | "bool" | "enum";
  editable: boolean;
  secret: boolean;
  requires_restart: boolean;
  runtime_effective: boolean;
  options: string[] | null;
  min_value: number | null;
  max_value: number | null;
}

export interface SystemSettingSchemaResponse {
  groups: Record<string, string>;
  items: SystemSettingSchemaItem[];
}

export interface SystemSettingEffectiveItem {
  key: string;
  name: string;
  category: string;
  value_type: "string" | "int" | "bool" | "enum";
  value: string | number | boolean | null;
  configured: boolean;
  source: "database" | "system" | "default";
  editable: boolean;
  secret: boolean;
  requires_restart: boolean;
  pending_restart: boolean;
  is_valid: boolean;
  invalid_reason: string | null;
  updated_at: string | null;
}

export interface SystemSettingEffectiveResponse {
  items: SystemSettingEffectiveItem[];
  pending_restart_count: number;
  database_override_count: number;
  credential_encryption_configured: boolean;
  systemd_managed: boolean;
}

export interface SystemSettingGroupUpdateResponse {
  group: string;
  updated_keys: string[];
  requires_restart: boolean;
  pending_restart_count: number;
  items: SystemSettingEffectiveItem[];
}

export interface SystemSettingResetResponse {
  key: string;
  source: string;
  requires_restart: boolean;
  pending_restart_count: number;
}

export interface SystemSettingChangeRead {
  id: number;
  setting_key: string;
  category: string;
  action: string;
  old_source: string | null;
  new_source: string | null;
  old_value_snapshot: string | null;
  new_value_snapshot: string | null;
  is_secret: boolean;
  requires_restart: boolean;
  pending_restart_after_change: boolean;
  actor_user_id: number | null;
  actor_username: string | null;
  client_ip: string | null;
  created_at: string;
}

export interface SystemSettingChangeListResponse {
  total: number;
  items: SystemSettingChangeRead[];
}

export type AlertSeverity = "warning" | "critical";
export type AlertStatus = "open" | "acknowledged" | "resolved";
export type AlertSourceType = "device" | "metric" | "scheduled_task" | "update_task";

export interface AlertRead {
  id: number;
  title: string;
  message: string;
  severity: AlertSeverity;
  status: AlertStatus;
  source_type: AlertSourceType;
  alert_type: string;
  device_id: number | null;
  scheduled_task_id: number | null;
  update_task_id: number | null;
  metric_name: string | null;
  metric_value: number | null;
  threshold_value: number | null;
  dedupe_key: string;
  acknowledged_by_user_id: number | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertListResponse {
  total: number;
  items: AlertRead[];
}

export interface AlertSummaryResponse {
  active_count: number;
  critical_count: number;
  unacknowledged_count: number;
  latest_alert_at: string | null;
  by_source: Record<string, number>;
  by_severity: Record<string, number>;
}

export interface AlertAcknowledgeRequest {
  note?: string | null;
}

export interface AlertResolveRequest {
  note?: string | null;
}

export interface AlertRuleRead {
  id: number;
  rule_type: string;
  enabled: boolean;
  severity: AlertSeverity;
  threshold_value: number | null;
  window_minutes: number | null;
  created_at: string;
  updated_at: string;
}

export type AlertRuleUpdateRequest = Partial<Pick<AlertRuleRead, "enabled" | "severity" | "threshold_value" | "window_minutes">>;

export interface AlertRuleListResponse {
  total: number;
  items: AlertRuleRead[];
}

export type AlertNotificationChannelType = "webhook";
export type AlertNotificationEventType = "triggered" | "acknowledged" | "resolved" | "auto_resolved";
export type AlertNotificationDeliveryStatus = "pending" | "success" | "failed" | "retrying" | "skipped";

export interface AlertNotificationChannelRead {
  id: number;
  name: string;
  channel_type: AlertNotificationChannelType | string;
  enabled: boolean;
  webhook_url_preview: string | null;
  timeout_seconds: number;
  header_keys: string[];
  secret_configured: boolean;
  last_test_status: string | null;
  last_test_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertNotificationChannelListResponse {
  total: number;
  items: AlertNotificationChannelRead[];
}

export interface AlertNotificationChannelCreateRequest {
  name: string;
  channel_type?: AlertNotificationChannelType;
  enabled?: boolean;
  webhook_url: string;
  headers?: Record<string, string>;
  timeout_seconds?: number;
}

export type AlertNotificationChannelUpdateRequest = Partial<
  Pick<AlertNotificationChannelCreateRequest, "name" | "enabled" | "webhook_url" | "headers" | "timeout_seconds">
>;

export interface AlertNotificationPolicyRead {
  id: number;
  name: string;
  enabled: boolean;
  channel_id: number;
  min_severity: AlertSeverity | string;
  source_types: string[];
  alert_statuses: string[];
  event_types: string[];
  created_at: string;
  updated_at: string;
}

export interface AlertNotificationPolicyListResponse {
  total: number;
  items: AlertNotificationPolicyRead[];
}

export interface AlertNotificationPolicyCreateRequest {
  name: string;
  enabled?: boolean;
  channel_id: number;
  min_severity?: AlertSeverity;
  source_types?: AlertSourceType[];
  alert_statuses?: AlertStatus[];
  event_types?: AlertNotificationEventType[];
}

export type AlertNotificationPolicyUpdateRequest = Partial<AlertNotificationPolicyCreateRequest>;

export interface AlertNotificationDeliveryRead {
  id: number;
  alert_id: number;
  channel_id: number;
  policy_id: number;
  event_type: AlertNotificationEventType | string;
  status: AlertNotificationDeliveryStatus | string;
  attempt_count: number;
  last_attempt_at: string | null;
  next_retry_at: string | null;
  response_status_code: number | null;
  response_summary: string | null;
  error_message: string | null;
  alert_title: string | null;
  channel_name: string | null;
  policy_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertNotificationDeliveryListResponse {
  total: number;
  items: AlertNotificationDeliveryRead[];
}

export interface AlertNotificationSummaryResponse {
  enabled_channel_count: number;
  enabled_policy_count: number;
  failed_delivery_count: number;
  retrying_delivery_count: number;
  last_delivery_at: string | null;
  warnings: string[];
}

export interface ListAlertsParams {
  offset?: number;
  limit?: number;
  status?: AlertStatus | "";
  severity?: AlertSeverity | "";
  source_type?: AlertSourceType | "";
  device_id?: number;
  alert_type?: string;
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

export async function getCurrentUser(): Promise<CurrentUserResponse> {
  const response = await api.get<CurrentUserResponse>("/auth/me");
  return response.data;
}

export async function listUsers(): Promise<UserListResponse> {
  const response = await api.get<UserListResponse>("/users");
  return response.data;
}

export async function createUser(payload: UserCreateRequest): Promise<UserRead> {
  const response = await api.post<UserRead>("/users", payload);
  return response.data;
}

export async function updateUser(userId: number, payload: UserUpdateRequest): Promise<UserRead> {
  const response = await api.put<UserRead>(`/users/${userId}`, payload);
  return response.data;
}

export async function resetUserPassword(userId: number, payload: UserResetPasswordRequest): Promise<UserRead> {
  const response = await api.post<UserRead>(`/users/${userId}/reset-password`, payload);
  return response.data;
}

export async function toggleUser(userId: number, isActive: boolean): Promise<UserRead> {
  const response = await api.post<UserRead>(`/users/${userId}/toggle`, { is_active: isActive });
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

export async function previewUpdateTaskTargets(payload: UpdateTaskTargetPreviewRequest): Promise<UpdateTaskTargetPreviewResponse> {
  const response = await api.post<UpdateTaskTargetPreviewResponse>("/update-tasks/preview-targets", payload);
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

export async function exportUpdateTaskResults(taskId: number): Promise<Blob> {
  const response = await api.get(`/update-tasks/${taskId}/export`, { responseType: "blob" });
  return response.data;
}

export async function listUpdateTaskTemplates(): Promise<UpdateTaskTemplateListResponse> {
  const response = await api.get<UpdateTaskTemplateListResponse>("/update-task-templates");
  return response.data;
}

export async function createUpdateTaskTemplate(payload: UpdateTaskTemplateCreateRequest): Promise<UpdateTaskTemplateRead> {
  const response = await api.post<UpdateTaskTemplateRead>("/update-task-templates", payload);
  return response.data;
}

export async function updateUpdateTaskTemplate(
  templateId: number,
  payload: UpdateTaskTemplateUpdateRequest,
): Promise<UpdateTaskTemplateRead> {
  const response = await api.put<UpdateTaskTemplateRead>(`/update-task-templates/${templateId}`, payload);
  return response.data;
}

export async function deleteUpdateTaskTemplate(templateId: number): Promise<void> {
  await api.delete(`/update-task-templates/${templateId}`);
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

export async function runScheduledTaskNow(taskId: number): Promise<ScheduledTaskExecuteResponse> {
  const response = await api.post<ScheduledTaskExecuteResponse>(`/scheduled-tasks/${taskId}/run-now`);
  return response.data;
}

export async function listScheduledTaskRuns(taskId: number): Promise<ScheduledTaskRunListResponse> {
  const response = await api.get<ScheduledTaskRunListResponse>(`/scheduled-tasks/${taskId}/runs`);
  return response.data;
}

export async function listScheduledTaskLogs(taskId: number): Promise<OperationLogListResponse> {
  const response = await api.get<OperationLogListResponse>(`/scheduled-tasks/${taskId}/logs`);
  return response.data;
}

export async function getSchedulerStatus(): Promise<SchedulerStatusResponse> {
  const response = await api.get<SchedulerStatusResponse>("/scheduler/status");
  return response.data;
}

export async function listAlerts(params?: ListAlertsParams): Promise<AlertListResponse> {
  const response = await api.get<AlertListResponse>("/alerts", { params });
  return response.data;
}

export async function getAlertSummary(): Promise<AlertSummaryResponse> {
  const response = await api.get<AlertSummaryResponse>("/alerts/summary");
  return response.data;
}

export async function acknowledgeAlert(alertId: number, payload: AlertAcknowledgeRequest = {}): Promise<AlertRead> {
  const response = await api.post<AlertRead>(`/alerts/${alertId}/acknowledge`, payload);
  return response.data;
}

export async function resolveAlert(alertId: number, payload: AlertResolveRequest = {}): Promise<AlertRead> {
  const response = await api.post<AlertRead>(`/alerts/${alertId}/resolve`, payload);
  return response.data;
}

export async function listAlertRules(): Promise<AlertRuleListResponse> {
  const response = await api.get<AlertRuleListResponse>("/alert-rules");
  return response.data;
}

export async function updateAlertRule(ruleId: number, payload: AlertRuleUpdateRequest): Promise<AlertRuleRead> {
  const response = await api.put<AlertRuleRead>(`/alert-rules/${ruleId}`, payload);
  return response.data;
}

export async function listAlertNotificationChannels(): Promise<AlertNotificationChannelListResponse> {
  const response = await api.get<AlertNotificationChannelListResponse>("/alert-notification-channels");
  return response.data;
}

export async function createAlertNotificationChannel(
  payload: AlertNotificationChannelCreateRequest,
): Promise<AlertNotificationChannelRead> {
  const response = await api.post<AlertNotificationChannelRead>("/alert-notification-channels", payload);
  return response.data;
}

export async function updateAlertNotificationChannel(
  channelId: number,
  payload: AlertNotificationChannelUpdateRequest,
): Promise<AlertNotificationChannelRead> {
  const response = await api.put<AlertNotificationChannelRead>(`/alert-notification-channels/${channelId}`, payload);
  return response.data;
}

export async function deleteAlertNotificationChannel(channelId: number): Promise<void> {
  await api.delete(`/alert-notification-channels/${channelId}`);
}

export async function testAlertNotificationChannel(channelId: number): Promise<AlertNotificationChannelRead> {
  const response = await api.post<AlertNotificationChannelRead>(`/alert-notification-channels/${channelId}/test`);
  return response.data;
}

export async function listAlertNotificationPolicies(): Promise<AlertNotificationPolicyListResponse> {
  const response = await api.get<AlertNotificationPolicyListResponse>("/alert-notification-policies");
  return response.data;
}

export async function createAlertNotificationPolicy(
  payload: AlertNotificationPolicyCreateRequest,
): Promise<AlertNotificationPolicyRead> {
  const response = await api.post<AlertNotificationPolicyRead>("/alert-notification-policies", payload);
  return response.data;
}

export async function updateAlertNotificationPolicy(
  policyId: number,
  payload: AlertNotificationPolicyUpdateRequest,
): Promise<AlertNotificationPolicyRead> {
  const response = await api.put<AlertNotificationPolicyRead>(`/alert-notification-policies/${policyId}`, payload);
  return response.data;
}

export async function deleteAlertNotificationPolicy(policyId: number): Promise<void> {
  await api.delete(`/alert-notification-policies/${policyId}`);
}

export async function listAlertNotificationDeliveries(): Promise<AlertNotificationDeliveryListResponse> {
  const response = await api.get<AlertNotificationDeliveryListResponse>("/alert-notification-deliveries", {
    params: { limit: 50 },
  });
  return response.data;
}

export async function retryAlertNotificationDelivery(deliveryId: number): Promise<AlertNotificationDeliveryRead> {
  const response = await api.post<AlertNotificationDeliveryRead>(`/alert-notification-deliveries/${deliveryId}/retry`);
  return response.data;
}

export async function getAlertNotificationSummary(): Promise<AlertNotificationSummaryResponse> {
  const response = await api.get<AlertNotificationSummaryResponse>("/alert-notification-summary");
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

export async function getSystemSettingSchema(): Promise<SystemSettingSchemaResponse> {
  const response = await api.get<SystemSettingSchemaResponse>("/system-settings/schema");
  return response.data;
}

export async function getEffectiveSystemSettings(): Promise<SystemSettingEffectiveResponse> {
  const response = await api.get<SystemSettingEffectiveResponse>("/system-settings/effective");
  return response.data;
}

export async function updateSystemSettingGroup(
  groupKey: string,
  values: Record<string, unknown>,
): Promise<SystemSettingGroupUpdateResponse> {
  const response = await api.put<SystemSettingGroupUpdateResponse>(`/system-settings/groups/${groupKey}`, { values });
  return response.data;
}

export async function resetSystemSetting(key: string): Promise<SystemSettingResetResponse> {
  const response = await api.post<SystemSettingResetResponse>(`/system-settings/${key}/reset`);
  return response.data;
}

export async function listSystemSettingChanges(): Promise<SystemSettingChangeListResponse> {
  const response = await api.get<SystemSettingChangeListResponse>("/system-settings/changes", { params: { limit: 50 } });
  return response.data;
}

export async function restartSystemService(confirmText: string): Promise<{ status: string; message: string }> {
  const response = await api.post<{ status: string; message: string }>("/system-settings/restart", {
    confirm_text: confirmText,
  });
  return response.data;
}

export function buildApiWebSocketUrl(path: string, token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const separator = path.includes("?") ? "&" : "?";
  return `${protocol}//${window.location.host}${path}${separator}token=${encodeURIComponent(token)}`;
}
