import { api, ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, AUTH_EXPIRED_EVENT, buildApiWebSocketUrl, type TokenResponse } from "./core";


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

