import { api } from "../core";

export interface FrpsImportRequest {
  dashboard_url: string;
  username: string;
  password: string;
  ssh_port_start: number;
  ssh_port_end: number;
  vnc_port_start: number;
  vnc_port_end: number;
  project_id: string;
  location?: string;
  overwrite_project_location?: boolean;
}

export interface FrpsDiscoveredDevice {
  name: string;
  device_sn: string;
  project_id: string;
  ssh_port: number;
  vnc_port: number | null;
  ssh_proxy_name: string;
  vnc_proxy_name: string | null;
  status: string;
  import_status: string;
  detail: string | null;
  existing_device_id: number | null;
}

export interface FrpsImportResponse {
  total: number;
  created: number;
  skipped: number;
  synced: number;
  conflicts: number;
  items: FrpsDiscoveredDevice[];
}

export async function discoverFrpsDevices(payload: FrpsImportRequest): Promise<FrpsImportResponse> {
  const response = await api.post<FrpsImportResponse>("/frps/discover", payload);
  return response.data;
}

export async function importFrpsDevices(payload: FrpsImportRequest): Promise<FrpsImportResponse> {
  const response = await api.post<FrpsImportResponse>("/frps/import", payload);
  return response.data;
}
