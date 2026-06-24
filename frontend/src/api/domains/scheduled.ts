import { api } from "../core";
import { type OperationLogListResponse } from "./logs";

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
