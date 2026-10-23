import { request } from "@/lib/api";

export type ExecutionCapabilities = {
  direct_execution: boolean;
  terrakube: boolean;
  terrakube_configured: boolean;
  terrakube_operations: string[];
};
export type ExecutionBinding = {
  backend: "eolgae_direct" | "terrakube";
  workspace_id: string | null;
  direct_execution: boolean;
};
export type RemoteWorkspace = {
  id: string; name: string; branch: string | null; folder: string | null;
  terraform_version: string | null; url: string | null;
};
export type RemoteJob = {
  id: string; status: string; created_at: string | null; commit: string | null; url: string | null;
};
export const getExecutionCapabilities = () => request<ExecutionCapabilities>("/execution/capabilities");
export const getExecutionBinding = (id: string) => request<ExecutionBinding>(`/canvas/${id}/execution`);
export const getRemoteWorkspaces = () => request<{
  items: RemoteWorkspace[]; errors: { workspace_id: string; status: number; message: string }[];
}>("/integrations/terrakube/workspaces");
export const getRemoteJobs = (id: string) => request<{items: RemoteJob[]; has_more: boolean}>(
  `/integrations/terrakube/workspaces/${id}/jobs`,
);
export const bindRemoteWorkspace = (canvasId: string, workspaceId: string) => request<ExecutionBinding>(
  `/canvas/${canvasId}/execution/terrakube`,
  { method: "PUT", body: JSON.stringify({ workspace_id: workspaceId }) },
);
