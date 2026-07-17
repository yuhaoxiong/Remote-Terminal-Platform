import { api } from "../core";

export interface ProjectRead {
  id: number;
  code: string;
  name: string;
  description: string | null;
  status: "active" | "archived" | string;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  total: number;
  items: ProjectRead[];
}

export interface HardwareProfileRead {
  id: number;
  code: string;
  name: string;
  soc: string;
  memory_mb: number;
  os_version: string;
  rknn_version: string | null;
  active: boolean;
}

export interface HardwareProfileListResponse {
  total: number;
  items: HardwareProfileRead[];
}

export interface FunctionRead {
  id: number;
  code: string;
  name: string;
  description: string | null;
  status: "active" | "archived" | string;
  created_at: string;
  updated_at: string;
}

export interface FunctionListResponse {
  total: number;
  items: FunctionRead[];
}

export interface FunctionReleaseRead {
  id: number;
  function_id: number;
  version: string;
  status: "draft" | "published" | "archived" | string;
  manifest_json: Record<string, unknown> | null;
  release_notes: string | null;
  published_at: string | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface FunctionReleaseListResponse {
  total: number;
  items: FunctionReleaseRead[];
}

export interface FunctionVariantRead {
  id: number;
  release_id: number;
  hardware_profile_id: number;
  artifact_uri: string;
  artifact_sha256: string;
  artifact_size: number;
  signature: string | null;
  key_id: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface FunctionVariantListResponse {
  total: number;
  items: FunctionVariantRead[];
}

export interface ProjectFunctionRead {
  id: number;
  project_id: number;
  function_id: number;
  desired_release_id: number;
  config_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectFunctionListResponse {
  total: number;
  items: ProjectFunctionRead[];
}

export async function listProjects(): Promise<ProjectListResponse> {
  const response = await api.get<ProjectListResponse>("/projects");
  return response.data;
}

export async function createProject(payload: { code: string; name: string; description?: string }): Promise<ProjectRead> {
  const response = await api.post<ProjectRead>("/projects", payload);
  return response.data;
}

export async function updateProject(
  projectId: number,
  payload: { name?: string; description?: string | null; status?: "active" | "archived" },
): Promise<ProjectRead> {
  const response = await api.put<ProjectRead>(`/projects/${projectId}`, payload);
  return response.data;
}

export async function listHardwareProfiles(): Promise<HardwareProfileListResponse> {
  const response = await api.get<HardwareProfileListResponse>("/hardware-profiles");
  return response.data;
}

export async function listFunctions(): Promise<FunctionListResponse> {
  const response = await api.get<FunctionListResponse>("/functions");
  return response.data;
}

export async function createFunction(payload: { code: string; name: string; description?: string }): Promise<FunctionRead> {
  const response = await api.post<FunctionRead>("/functions", payload);
  return response.data;
}

export async function updateFunction(
  functionId: number,
  payload: { name?: string; description?: string | null; status?: "active" | "archived" },
): Promise<FunctionRead> {
  const response = await api.put<FunctionRead>(`/functions/${functionId}`, payload);
  return response.data;
}

export async function listFunctionReleases(functionId: number): Promise<FunctionReleaseListResponse> {
  const response = await api.get<FunctionReleaseListResponse>(`/functions/${functionId}/releases`);
  return response.data;
}

export async function createFunctionRelease(
  functionId: number,
  payload: { version: string; release_notes?: string; manifest_json?: Record<string, unknown> },
): Promise<FunctionReleaseRead> {
  const response = await api.post<FunctionReleaseRead>(`/functions/${functionId}/releases`, payload);
  return response.data;
}

export async function listFunctionVariants(
  functionId: number,
  releaseId: number,
): Promise<FunctionVariantListResponse> {
  const response = await api.get<FunctionVariantListResponse>(
    `/functions/${functionId}/releases/${releaseId}/variants`,
  );
  return response.data;
}

export async function createFunctionVariant(
  functionId: number,
  releaseId: number,
  payload: {
    hardware_profile_id: number;
    artifact_uri: string;
    artifact_sha256: string;
    artifact_size: number;
    signature?: string;
    key_id?: string;
  },
): Promise<FunctionVariantRead> {
  const response = await api.post<FunctionVariantRead>(
    `/functions/${functionId}/releases/${releaseId}/variants`,
    payload,
  );
  return response.data;
}

export async function publishFunctionRelease(functionId: number, releaseId: number): Promise<FunctionReleaseRead> {
  const response = await api.post<FunctionReleaseRead>(`/functions/${functionId}/releases/${releaseId}/publish`);
  return response.data;
}

export async function listProjectFunctions(projectId: number): Promise<ProjectFunctionListResponse> {
  const response = await api.get<ProjectFunctionListResponse>(`/projects/${projectId}/functions`);
  return response.data;
}

export async function setProjectFunction(
  projectId: number,
  functionId: number,
  payload: { desired_release_id: number; config_json?: Record<string, unknown> },
): Promise<ProjectFunctionRead> {
  const response = await api.put<ProjectFunctionRead>(`/projects/${projectId}/functions/${functionId}`, payload);
  return response.data;
}

export async function markProjectFunctionPendingUninstall(
  projectId: number,
  functionId: number,
): Promise<ProjectFunctionRead> {
  const response = await api.post<ProjectFunctionRead>(
    `/projects/${projectId}/functions/${functionId}/pending-uninstall`,
  );
  return response.data;
}
