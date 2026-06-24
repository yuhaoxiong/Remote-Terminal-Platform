import { api } from "../core";

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
