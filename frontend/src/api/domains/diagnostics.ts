import { api } from "../core";

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

export async function getDiagnosticsConfig(): Promise<DiagnosticsConfigResponse> {
  const response = await api.get<DiagnosticsConfigResponse>("/diagnostics/config");
  return response.data;
}
