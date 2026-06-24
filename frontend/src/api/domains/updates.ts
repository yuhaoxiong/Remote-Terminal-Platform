import { api } from "../core";

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
