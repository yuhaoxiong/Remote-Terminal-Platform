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
