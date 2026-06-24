import { api } from "../core";

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
