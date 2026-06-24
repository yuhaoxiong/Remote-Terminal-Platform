import { api, type TokenResponse } from "../core";

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
