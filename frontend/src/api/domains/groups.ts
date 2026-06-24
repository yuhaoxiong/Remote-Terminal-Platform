import { api } from "../core";

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
