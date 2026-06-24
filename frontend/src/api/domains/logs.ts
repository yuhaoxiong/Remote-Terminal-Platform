import { api } from "../core";

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

export async function listLogs(params?: ListLogsParams): Promise<OperationLogListResponse> {
  const response = await api.get<OperationLogListResponse>("/logs", { params });
  return response.data;
}

export async function exportLogs(params?: Omit<ListLogsParams, "offset" | "limit">): Promise<Blob> {
  const response = await api.get<Blob>("/logs/export", { params, responseType: "blob" });
  return response.data;
}
