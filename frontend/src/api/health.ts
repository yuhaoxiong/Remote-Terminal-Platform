import axios from "axios";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await axios.get<HealthResponse>("/api/health");
  return response.data;
}
