import { api } from "../core";

export interface DeploymentPlanItemRead {
  id: number;
  plan_id: number;
  device_id: number;
  function_id: number;
  release_id: number;
  variant_id: number;
  config_snapshot: Record<string, unknown> | null;
  config_hash: string;
  artifact_sha256: string;
  preflight_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface DeploymentPlanRead {
  id: number;
  project_id: number;
  status: string;
  snapshot_hash: string;
  expires_at: string;
  stale_reason: string | null;
  created_by: number;
  confirmed_by: number | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  items: DeploymentPlanItemRead[];
}

export interface DeploymentExecutionItemRead {
  id: number;
  deployment_execution_id: number;
  plan_item_id: number;
  status: string;
  attempt_count: number;
  result_json: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeploymentExecutionRead {
  id: number;
  execution_id: string;
  plan_id: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  created_by: number;
  created_at: string;
  updated_at: string;
  items: DeploymentExecutionItemRead[];
}

export async function createDeploymentPlan(projectId: number, deviceIds: number[]): Promise<DeploymentPlanRead> {
  const response = await api.post<DeploymentPlanRead>(`/projects/${projectId}/deployment-plans`, {
    device_ids: deviceIds,
  });
  return response.data;
}

export async function getDeploymentPlan(planId: number): Promise<DeploymentPlanRead> {
  const response = await api.get<DeploymentPlanRead>(`/deployment-plans/${planId}`);
  return response.data;
}

export async function confirmDeploymentPlan(planId: number): Promise<DeploymentExecutionRead> {
  const response = await api.post<DeploymentExecutionRead>(`/deployment-plans/${planId}/confirm`);
  return response.data;
}

export async function getDeploymentExecution(executionId: string): Promise<DeploymentExecutionRead> {
  const response = await api.get<DeploymentExecutionRead>(`/deployment-executions/${executionId}`);
  return response.data;
}

export async function executeDeploymentExecution(executionId: string): Promise<DeploymentExecutionRead> {
  const response = await api.post<DeploymentExecutionRead>(`/deployment-executions/${executionId}/execute`);
  return response.data;
}
