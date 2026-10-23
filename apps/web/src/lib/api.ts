// Eolgae API client.
// 백엔드 schema 와 동일 (snake_case). 자세한 schema: docs/specs/CANVAS-SCHEMA.md

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ===== Auth token store (모듈 스코프) =====
// AuthContext 에서 set/clear. request() 가 매 호출마다 참조.
// SSR 안전성: Next.js client component 만에서 사용. 모듈 1회 평가됨.

let _accessToken: string | null = null;
let _onUnauthorized: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  _onUnauthorized = handler;
}

/**
 * 401 응답 시 /auth/refresh 1회 시도 → 성공하면 새 access_token 으로 원 요청 retry.
 * 실패하면 unauthorized handler 호출 (AuthContext 에서 로그아웃 처리).
 */
let _refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include", // refresh cookie 전송
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) return null;
      const data: TokenResponse = await res.json();
      _accessToken = data.access_token;
      return data.access_token;
    } catch {
      return null;
    } finally {
      _refreshInFlight = null;
    }
  })();
  return _refreshInFlight;
}

export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface CanvasNode {
  id: string;
  type: string;
  display_name?: string;
  position: Position;
  size?: Size;
  properties?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  parent_group_id?: string | null;
  aws_binding?: Record<string, unknown> | null;
}

export interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface CanvasGroup {
  id: string;
  type: string;
  display_name?: string;
  position: Position;
  size?: Size;
  contained_node_ids?: string[];
  properties?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  parent_group_id?: string | null;
}

export interface CanvasGraph {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  groups: CanvasGroup[];
}

export interface AwsAccount {
  aws_connection_id?: string | null;
  account_id?: string | null;
  default_region: string;
  default_tags: Record<string, string>;
  external_id?: string | null;
  role_arn?: string | null;
  binding_status?: string | null;
  last_verified_at?: string | null;
  assumed_arn?: string | null;
}

export type DeploymentStatus =
  | "queued"
  | "planning"
  | "success"
  | "approved"
  | "applying"
  | "applied"
  | "destroying"
  | "destroyed"
  | "failed";

export type CanvasState = "design" | "deploy" | "running" | "applied" | "destroyed";
export type CanvasKind = "aws" | "kubernetes" | "multi_architecture";

export interface Canvas {
  id: string;
  name: string;
  description?: string | null;
  schema_version: string;
  state: CanvasState;
  canvas_kind: CanvasKind;
  graph: CanvasGraph;
  aws_connection_id?: string | null;
  aws_account?: AwsAccount | null;
  group_id?: string | null;
  environment_id?: string | null;
  target_id?: string | null;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
}

export interface CanvasCreatePayload {
  name?: string;
  description?: string;
  state?: CanvasState;
  canvas_kind?: CanvasKind;
  graph?: CanvasGraph;
  aws_connection_id?: string | null;
  aws_account?: AwsAccount;
  group_id?: string | null;
  environment_id?: string | null;
  target_id?: string | null;
}

export interface CanvasUpdatePayload {
  name?: string;
  description?: string;
  state?: CanvasState;
  graph?: CanvasGraph;
  aws_connection_id?: string | null;
  aws_account?: AwsAccount | null;
  group_id?: string | null;
  environment_id?: string | null;
  target_id?: string | null;
}

export interface CanvasTemplate {
  id: string;
  name: string;
  description: string;
  node_count: number;
  edge_count: number;
}

export interface CanvasFragment {
  id: string;
  name: string;
  description: string;
  node_count: number;
  edge_count: number;
}

export interface CanvasFromTemplatePayload {
  template_id: string;
  name?: string | null;
  aws_connection_id?: string | null;
  group_id?: string | null;
  environment_id?: string | null;
}

export interface CanvasInsertFragmentPayload {
  fragment_id: string;
  x?: number;
  y?: number;
}

interface ApiErrorDetail {
  code?: string;
  message?: string;
}
export class ApiError extends Error {
  status: number;
  code: string | null;
  constructor(status: number, message: string, code: string | null = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function authHeaders(): HeadersInit {
  return _accessToken ? { Authorization: `Bearer ${_accessToken}` } : {};
}

async function _rawRequest(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    credentials: "include", // refresh cookie 가 같은 origin/Caddy proxy 일 때 통과
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
    ...init,
  });
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res = await _rawRequest(path, init);

  // 401 → refresh 1회 시도 → retry
  if (res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await _rawRequest(path, init);
    } else {
      _onUnauthorized?.();
    }
  }

  if (!res.ok) {
    // detail 형태가 두 가지:
    //  - HTTPException: { detail: { code, message } } (우리 라우터)
    //  - RequestValidationError(422): { detail: [{ loc, msg, type }, ...] }
    let code: string | null = null;
    let message = `${init?.method || "GET"} ${path} failed: ${res.status}`;
    try {
      const data = await res.json();
      const detail = data?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        // 422 validation error — 첫 항목의 필드+사유를 사람이 읽을 메시지로
        code = "validation_error";
        const first = detail[0];
        if (first) {
          const field = Array.isArray(first.loc)
            ? first.loc[first.loc.length - 1]
            : undefined;
          message = field ? `${field}: ${first.msg}` : String(first.msg);
        }
      } else if (detail && typeof detail === "object") {
        const d = detail as ApiErrorDetail;
        code = d.code ?? null;
        if (d.message) message = d.message;
      }
    } catch {
      // ignore
    }
    throw new ApiError(res.status, message, code);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function listCanvases(): Promise<Canvas[]> {
  return request<Canvas[]>("/canvas");
}

export async function createCanvas(payload: CanvasCreatePayload = {}): Promise<Canvas> {
  return request<Canvas>("/canvas", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listCanvasTemplates(): Promise<CanvasTemplate[]> {
  return request<CanvasTemplate[]>("/canvas/templates");
}

export async function createCanvasFromTemplate(
  payload: CanvasFromTemplatePayload,
): Promise<Canvas> {
  return request<Canvas>("/canvas/from-template", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listCanvasFragments(): Promise<CanvasFragment[]> {
  return request<CanvasFragment[]>("/canvas/fragments");
}

export async function insertCanvasFragment(
  canvasId: string,
  payload: CanvasInsertFragmentPayload,
): Promise<Canvas> {
  return request<Canvas>(`/canvas/${canvasId}/fragments`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getCanvas(id: string): Promise<Canvas> {
  return request<Canvas>(`/canvas/${id}`);
}

export async function updateCanvas(
  id: string,
  payload: CanvasUpdatePayload,
): Promise<Canvas> {
  return request<Canvas>(`/canvas/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteCanvas(id: string): Promise<void> {
  // request() wrapper 경유 — Authorization 헤더 + 401 refresh retry + 204 처리.
  await request<void>(`/canvas/${id}`, { method: "DELETE" });
}

export async function duplicateCanvas(
  id: string,
  payload: { name?: string | null } = {},
): Promise<Canvas> {
  return request<Canvas>(`/canvas/${id}/duplicate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listTrash(): Promise<Canvas[]> {
  return request<Canvas[]>("/canvas/trash");
}

export async function restoreCanvas(id: string): Promise<Canvas> {
  return request<Canvas>(`/canvas/${id}/restore`, { method: "POST" });
}

export async function permanentDeleteCanvas(id: string): Promise<void> {
  await request<void>(`/canvas/${id}/permanent`, { method: "DELETE" });
}

export interface TofuGenerationResult {
  tf: string;
  filename: string;
}

export interface KubernetesYamlGenerationResult {
  yaml: string;
  filename: string;
}

export interface KubernetesValidationIssue {
  severity: "error" | "warning" | string;
  code: string;
  message: string;
  node_id?: string | null;
}

export interface KubernetesValidationResult {
  ok: boolean;
  mode: string;
  target_id?: string | null;
  issues: KubernetesValidationIssue[];
  summary: {
    resources: number;
    errors: number;
    warnings: number;
  };
  yaml: string;
  dry_run?: {
    mode: string;
    ready?: boolean;
    blocked_by?: string | null;
    target_id?: string | null;
    namespace?: string | null;
    message: string;
  };
}

export interface TofuPlanStep {
  step: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_sec: number;
}

export interface DeploymentProgressEvent {
  step: string;
  label: string;
  status: "running" | "success" | "warning" | "failed" | string;
  message?: string | null;
  timestamp?: string | null;
}

export interface ValidationIssue {
  node_id?: string | null;
  node_type?: string | null;
  display_name?: string | null;
  severity: "error" | "warning" | string;
  field?: string | null;
  message: string;
  suggested_action?: string | null;
}

export interface TofuPlanResult {
  ok: boolean;
  error?: string | null;
  steps: TofuPlanStep[];
  work_dir: string;
  plan_text?: string | null;
  validation_issues?: ValidationIssue[] | null;
  apply_ready?: boolean;
  apply_readiness_note?: string | null;
  deployment_id?: string;
  deployment_status?: PlanDeploymentStatus;
  assumed_arn?: string | null;
}

export type PlanDeploymentStatus = DeploymentStatus;

export interface PlanDeployment {
  id: string;
  canvas_id: string;
  canvas_version_id: string;
  status: PlanDeploymentStatus;
  mode: "plan" | "apply" | "destroy";
  plan_result?: TofuPlanResult | null;
  plan_artifact?: Record<string, unknown> | null;
  state_backend?: Record<string, unknown> | null;
  progress_events?: DeploymentProgressEvent[];
  error_message?: string | null;
  assumed_arn?: string | null;
  source_plan_deployment_id?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
}

export interface DeploymentSummary {
  total: number;
  approval_pending: number;
  failed: number;
  active: number;
  applied: number;
  destroyed: number;
  recent: DeploymentSummaryItem[];
}

export interface DeploymentSummaryItem {
  id: string;
  canvas_id: string;
  mode: "plan" | "apply" | "destroy" | string;
  status: DeploymentStatus;
  created_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  requires_approval: boolean;
  source_plan_deployment_id?: string | null;
}

export interface CanvasDeploymentHistory {
  canvas_id: string;
  total_returned: number;
  items: DeploymentSummaryItem[];
}

export interface AwsBootstrapResult {
  account_id: string;
  region: string;
  external_id: string;
  eolgae_account_id: string;
  role_arn?: string | null;
  binding_status?: string | null;
  cloudformation_template: string;
  cloudformation_quick_create_url?: string | null;
}

export interface AwsVerifyResult {
  ok: boolean;
  status: string;
  message: string;
  assumed_arn?: string | null;
}

export async function generateTofu(id: string): Promise<TofuGenerationResult> {
  return request<TofuGenerationResult>(`/canvas/${id}/generate-tofu`, {
    method: "POST",
  });
}

export async function generateKubernetesYaml(
  id: string,
): Promise<KubernetesYamlGenerationResult> {
  return request<KubernetesYamlGenerationResult>(
    `/canvas/${id}/generate-kubernetes-yaml`,
    { method: "POST" },
  );
}

export async function validateKubernetesCanvas(
  id: string,
): Promise<KubernetesValidationResult> {
  return request<KubernetesValidationResult>(
    `/canvas/${id}/validate-kubernetes`,
    { method: "POST" },
  );
}

export async function runTofuPlan(id: string): Promise<TofuPlanResult> {
  const deployment = await startTofuPlan(id);

  for (let attempt = 0; attempt < 180; attempt += 1) {
    const current =
      attempt === 0
        ? deployment
        : await request<PlanDeployment>(
            `/canvas/${id}/deployments/${deployment.id}`,
          );
    if (current.status === "success" && current.plan_result) {
      return {
        ...current.plan_result,
        deployment_id: current.id,
        deployment_status: current.status,
        assumed_arn: current.assumed_arn,
      };
    }
    if (current.status === "failed") {
      return {
        ...(current.plan_result || {
          ok: false,
          steps: [],
          work_dir: "",
          plan_text: null,
        }),
        ok: false,
        error:
          current.error_message ||
          current.plan_result?.error ||
          "비동기 Plan 실패",
        deployment_id: current.id,
        deployment_status: current.status,
        assumed_arn: current.assumed_arn,
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  throw new Error("Plan 실행이 6분 안에 완료되지 않음");
}

export async function startTofuPlan(id: string): Promise<PlanDeployment> {
  return request<PlanDeployment>(`/canvas/${id}/deployments/plan`, {
    method: "POST",
  });
}

export async function getDeploymentSummary(): Promise<DeploymentSummary> {
  return request<DeploymentSummary>("/canvas/deployments/summary");
}

export async function getCanvasDeploymentHistory(
  canvasId: string,
  limit = 20,
): Promise<CanvasDeploymentHistory> {
  return request<CanvasDeploymentHistory>(
    `/canvas/${canvasId}/deployments/history?limit=${encodeURIComponent(limit)}`,
  );
}

export async function startDestroyPlan(id: string): Promise<PlanDeployment> {
  return request<PlanDeployment>(`/canvas/${id}/deployments/destroy-plan`, {
    method: "POST",
  });
}

export async function getPlanDeployment(
  canvasId: string,
  deploymentId: string,
): Promise<PlanDeployment> {
  return request<PlanDeployment>(
    `/canvas/${canvasId}/deployments/${deploymentId}`,
  );
}

export async function approvePlanDeployment(
  canvasId: string,
  deploymentId: string,
): Promise<PlanDeployment> {
  return request<PlanDeployment>(
    `/canvas/${canvasId}/deployments/${deploymentId}/approve`,
    { method: "POST" },
  );
}

export async function startApplyDeployment(
  canvasId: string,
  deploymentId: string,
): Promise<PlanDeployment> {
  return request<PlanDeployment>(
    `/canvas/${canvasId}/deployments/${deploymentId}/apply`,
    { method: "POST" },
  );
}

export async function startDestroyDeployment(
  canvasId: string,
  deploymentId: string,
): Promise<PlanDeployment> {
  return request<PlanDeployment>(
    `/canvas/${canvasId}/deployments/${deploymentId}/destroy`,
    { method: "POST" },
  );
}

export async function runLegacySynchronousTofuPlan(
  id: string,
): Promise<TofuPlanResult> {
  return request<TofuPlanResult>(`/canvas/${id}/plan`, {
    method: "POST",
  });
}

export async function bootstrapAwsAccount(
  id: string,
  payload: { account_id: string; region: string },
): Promise<AwsBootstrapResult> {
  return request<AwsBootstrapResult>(`/canvas/${id}/aws/bootstrap`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveAwsRoleArn(
  id: string,
  roleArn: string,
): Promise<AwsAccount> {
  return request<AwsAccount>(`/canvas/${id}/aws/role`, {
    method: "PUT",
    body: JSON.stringify({ role_arn: roleArn }),
  });
}

export async function verifyAwsRole(id: string): Promise<AwsVerifyResult> {
  return request<AwsVerifyResult>(`/canvas/${id}/aws/verify`, {
    method: "POST",
  });
}

export type FeedbackSeverity = "critical" | "high" | "medium" | "low";
export type FeedbackCategory = "security" | "cost" | "ha" | "operations";
export type ReviewEnvironment = "unknown" | "dev" | "staging" | "production";
export type ReviewAvailabilityTarget =
  | "unknown"
  | "best_effort"
  | "business_hours"
  | "high_availability";
export type ReviewCostPosture =
  | "unknown"
  | "cheapest"
  | "balanced"
  | "production_safe";
export type ReviewTrafficExpectation =
  | "unknown"
  | "small"
  | "medium"
  | "high";

export interface ReviewContext {
  purpose: string;
  environment: ReviewEnvironment;
  availability_target: ReviewAvailabilityTarget;
  cost_posture: ReviewCostPosture;
  traffic_expectation: ReviewTrafficExpectation;
  notes: string;
}

export interface FeedbackItem {
  category: FeedbackCategory;
  severity: FeedbackSeverity;
  title: string;
  description: string;
  target_node_id?: string | null;
  target_edge_id?: string | null;
  recommendation?: string | null;
}

export interface FeedbackResponse {
  items: FeedbackItem[];
  summary: string;
  canvas_hash: string;
}

export async function requestFeedback(
  id: string,
  reviewContext?: ReviewContext,
): Promise<FeedbackResponse> {
  return request<FeedbackResponse>(`/canvas/${id}/feedback`, {
    method: "POST",
    body: JSON.stringify({ review_context: reviewContext ?? null }),
  });
}

// ===== Auth =====

export interface AuthUser {
  id: string;
  username: string;
  email: string | null;
  display_name: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  user: AuthUser;
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface SignupPayload {
  username: string;
  password: string;
  email?: string;
  display_name?: string;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

export async function signup(payload: SignupPayload): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<void> {
  await request<void>("/auth/logout", { method: "POST" });
}

export async function fetchMe(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export async function updateMe(payload: {
  display_name?: string;
  email?: string;
}): Promise<AuthUser> {
  return request<AuthUser>("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await request<void>("/auth/password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type OAuthProvider = "github" | "google";

export function buildOAuthStartUrl(
  provider: OAuthProvider,
  redirect: string = "/",
): string {
  const query = new URLSearchParams({ redirect });
  return `${API_URL}/auth/oauth/${provider}/start?${query.toString()}`;
}

// ===== Canvas Groups =====

export interface ApiCanvasGroup {
  id: string;
  owner_id: string;
  name: string;
  slug: string;
  description: string | null;
  color: string | null;
  status: string;
  default_environment_id?: string | null;
  default_environment?: EnvironmentSummary | null;
  default_aws_connection?: GroupAwsConnectionSummary | null;
  connected_aws_connections: GroupAwsConnectionSummary[];
  canvas_count: number;
  last_activity_at?: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface EnvironmentSummary {
  id: string;
  name: string;
  slug: string;
  risk_level: string;
}

export interface GroupAwsConnectionSummary {
  id: string;
  name: string;
  account_id: string;
  default_region: string;
  binding_status: string;
  permission_mode: string;
  is_default: boolean;
}

export interface CanvasInGroup {
  id: string;
  name: string;
  description: string | null;
  state: CanvasState;
  updated_at: string;
  deleted_at: string | null;
}

export interface CanvasGroupCreatePayload {
  name: string;
  slug?: string;
  description?: string;
  color?: string;
  default_environment_id?: string | null;
  sort_order?: number;
}

export interface CanvasGroupUpdatePayload {
  name?: string;
  slug?: string;
  description?: string;
  color?: string;
  status?: string;
  default_environment_id?: string | null;
  sort_order?: number;
}

export async function listGroups(): Promise<ApiCanvasGroup[]> {
  return request<ApiCanvasGroup[]>("/groups");
}

export async function createGroup(
  payload: CanvasGroupCreatePayload,
): Promise<ApiCanvasGroup> {
  return request<ApiCanvasGroup>("/groups", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getGroup(id: string): Promise<ApiCanvasGroup> {
  return request<ApiCanvasGroup>(`/groups/${id}`);
}

export async function updateGroup(
  id: string,
  payload: CanvasGroupUpdatePayload,
): Promise<ApiCanvasGroup> {
  return request<ApiCanvasGroup>(`/groups/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteGroup(id: string): Promise<void> {
  await request<void>(`/groups/${id}`, { method: "DELETE" });
}

export async function listGroupCanvases(
  id: string,
): Promise<CanvasInGroup[]> {
  return request<CanvasInGroup[]>(`/groups/${id}/canvases`);
}

export async function addCanvasToGroup(
  groupId: string,
  canvasId: string,
): Promise<CanvasInGroup> {
  return request<CanvasInGroup>(`/groups/${groupId}/canvases/${canvasId}`, {
    method: "POST",
  });
}

export async function removeCanvasFromGroup(
  groupId: string,
  canvasId: string,
): Promise<void> {
  await request<void>(`/groups/${groupId}/canvases/${canvasId}`, {
    method: "DELETE",
  });
}

export async function attachAwsConnectionToGroup(
  groupId: string,
  awsConnectionId: string,
  isDefault = false,
): Promise<GroupAwsConnectionSummary[]> {
  return request<GroupAwsConnectionSummary[]>(`/groups/${groupId}/aws-connections`, {
    method: "POST",
    body: JSON.stringify({
      aws_connection_id: awsConnectionId,
      is_default: isDefault,
    }),
  });
}

export async function setGroupDefaultAwsConnection(
  groupId: string,
  awsConnectionId: string,
): Promise<GroupAwsConnectionSummary[]> {
  return request<GroupAwsConnectionSummary[]>(
    `/groups/${groupId}/aws-connections/${awsConnectionId}/default`,
    { method: "PUT" },
  );
}

export async function detachAwsConnectionFromGroup(
  groupId: string,
  awsConnectionId: string,
): Promise<void> {
  await request<void>(`/groups/${groupId}/aws-connections/${awsConnectionId}`, {
    method: "DELETE",
  });
}

// ===== Environments =====

export interface Environment {
  id: string;
  owner_id: string;
  name: string;
  slug: string;
  description: string | null;
  risk_level: "low" | "medium" | "high";
  sort_order: number;
  archived_at: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EnvironmentCreatePayload {
  name: string;
  slug?: string;
  description?: string;
  risk_level?: "low" | "medium" | "high";
  sort_order?: number;
}

export async function listEnvironments(): Promise<Environment[]> {
  return request<Environment[]>("/environments");
}

export async function createEnvironment(
  payload: EnvironmentCreatePayload,
): Promise<Environment> {
  return request<Environment>("/environments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ===== Targets =====

export type TargetKind = "aws_account" | "kubernetes_cluster";
export type TargetStatus = "draft" | "pending" | "ready" | "error" | "archived";

export interface Target {
  id: string;
  owner_id: string;
  name: string;
  slug: string;
  kind: TargetKind;
  provider: string;
  status: TargetStatus;
  environment_id?: string | null;
  aws_connection_id?: string | null;
  endpoint?: string | null;
  config: Record<string, unknown>;
  secret_ref?: Record<string, unknown> | null;
  last_verified_at?: string | null;
  last_error?: string | null;
  archived_at?: string | null;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TargetCreatePayload {
  name: string;
  slug?: string;
  kind: TargetKind;
  provider?: "aws" | "kubernetes";
  environment_id?: string | null;
  aws_connection_id?: string | null;
  endpoint?: string | null;
  config?: Record<string, unknown>;
  secret_ref?: Record<string, unknown> | null;
}

export interface TargetVerificationCheck {
  name: string;
  ok: boolean;
  message: string;
}

export interface TargetVerifyResult {
  ok: boolean;
  mode: string;
  status: TargetStatus;
  message: string;
  checks: TargetVerificationCheck[];
  last_verified_at?: string | null;
}

export interface KubernetesReadOnlyManifest {
  namespace: string;
  service_account_name: string;
  cluster_role_name: string;
  cluster_role_binding_name: string;
  manifest: string;
  apply_command: string;
  token_command: string;
  ca_command: string;
  endpoint_command: string;
}

export async function listTargets(kind?: TargetKind): Promise<Target[]> {
  const suffix = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return request<Target[]>(`/targets${suffix}`);
}

export async function createTarget(payload: TargetCreatePayload): Promise<Target> {
  return request<Target>("/targets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function verifyTarget(id: string): Promise<TargetVerifyResult> {
  return request<TargetVerifyResult>(`/targets/${id}/verify`, {
    method: "POST",
  });
}

export async function getKubernetesReadOnlyManifest(): Promise<KubernetesReadOnlyManifest> {
  return request<KubernetesReadOnlyManifest>("/targets/kubernetes/read-only-manifest");
}

// ===== AWS Connections =====

export interface AwsConnection {
  id: string;
  name: string;
  account_id: string;
  default_region: string;
  external_id: string;
  role_arn?: string | null;
  binding_status: string;
  permission_mode: string;
  last_verify_error?: string | null;
  assumed_arn?: string | null;
  last_verified_at?: string | null;
  cloudformation_template?: string | null;
  cloudformation_quick_create_url?: string | null;
  connected_project_groups: Array<{
    id: string;
    name: string;
    slug: string;
    is_default: boolean;
  }>;
}

export interface AwsConnectionPreparePayload {
  account_id: string;
  region?: string;
}

export interface AwsConnectionVerifyResult {
  ok: boolean;
  status: string;
  message: string;
  assumed_arn?: string | null;
}

export async function listAwsConnections(): Promise<AwsConnection[]> {
  return request<AwsConnection[]>("/aws-connections");
}

export async function prepareAwsConnection(
  payload: AwsConnectionPreparePayload,
): Promise<AwsConnection> {
  return request<AwsConnection>("/aws-connections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function saveAwsConnectionRole(
  id: string,
  roleArn: string,
): Promise<AwsConnection> {
  return request<AwsConnection>(`/aws-connections/${id}/role`, {
    method: "PUT",
    body: JSON.stringify({ role_arn: roleArn }),
  });
}

export async function verifyAwsConnection(
  id: string,
): Promise<AwsConnectionVerifyResult> {
  return request<AwsConnectionVerifyResult>(`/aws-connections/${id}/verify`, {
    method: "POST",
  });
}

// ===== Settings =====

export interface ArtifactStorageSettings {
  backend: string;
  retention_policy: string;
  local_root?: string | null;
  s3_bucket?: string | null;
  s3_prefix?: string | null;
  s3_region?: string | null;
  s3_endpoint_url?: string | null;
  s3_force_path_style?: boolean | null;
}

export interface RuntimeSettings {
  artifact_storage: ArtifactStorageSettings;
}

export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  return request<RuntimeSettings>("/settings/runtime");
}
