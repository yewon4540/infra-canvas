import { request } from "@/lib/api";

export type RemotePlanRequest = { idempotency_key: string; commit_sha: string; canvas_revision: string };
export type RemotePlan = {
  id: string; canvas_version_id: string; canvas_revision: string; stale: boolean;
  commit_sha: string; workspace_id: string; template_id: string; template_sha256: string;
  operation: "plan"; status: string; job_id: string | null; error_message: string | null;
  created_at: string; updated_at: string;
  result: { job_id: string; remote_status: string; commit_sha: string | null; has_changes: boolean | null; url: string | null } | null;
};
export type RemotePlanList = { canvas_revision: string; plan_enabled: boolean; items: RemotePlan[] };
export const boundCanvases = (workspaceId: string) => request<{items: {id: string; name: string}[]}>(
  `/integrations/terrakube/workspaces/${workspaceId}/canvases`,
);
export const listRemotePlans = (id: string) => request<RemotePlanList>(`/canvas/${id}/remote-plans`);
export const submitRemotePlan = (id: string, body: RemotePlanRequest) => request<RemotePlan>(
  `/canvas/${id}/remote-plans`, {method:"POST", body:JSON.stringify(body)},
);
export const syncRemotePlan = (id: string, planId: string) => request<RemotePlan>(
  `/canvas/${id}/remote-plans/${planId}/sync`, {method:"POST"},
);
export const activeRemotePlan = (status: string) => ["submitting", "unknown", "pending", "running"].includes(status);
