import { api } from "../core";
import { type UserRole } from "./auth";

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
