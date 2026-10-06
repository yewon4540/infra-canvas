import { useEffect, useRef, type MouseEvent as ReactMouseEvent } from "react";
import { type Edge, type Node } from "@xyflow/react";

import { AwsAccountPanel } from "@/components/AwsAccountPanel";
import { EdgePropertiesPanel } from "@/components/EdgePropertiesPanel";
import { KubernetesResourceTree } from "@/components/KubernetesResourceTree";
import { PropertiesPanel } from "@/components/PropertiesPanel";
import { TfPreviewPanel } from "@/components/TfPreviewPanel";
import { TofuPlanPanel } from "@/components/TofuPlanPanel";
import { InspectorControls } from "@/components/canvas/InspectorControls";
import { InspectorSelectionHeader } from "@/components/canvas/InspectorSelectionHeader";
import { KubernetesValidationSummary } from "@/components/canvas/KubernetesValidationSummary";
import {
  type AwsAccount,
  type CanvasKind,
  type CanvasState,
  type DeploymentSummaryItem,
  type KubernetesValidationResult,
  type KubernetesYamlGenerationResult,
  type PlanDeployment,
  type TofuGenerationResult,
  type TofuPlanResult,
} from "@/lib/api";

type NodeUpdate = {
  display_name?: string;
  properties?: Record<string, unknown>;
  view?: Record<string, unknown>;
};

type EdgeUpdate = {
  type?: string;
  properties?: Record<string, unknown>;
};

type SecurityGroupOption = {
  id: string;
  name: string;
};

type CanvasSidePanelsProps = {
  canvasId?: string;
  canvasKind?: CanvasKind;
  canvasState?: CanvasState;
  awsAccount?: AwsAccount | null;
  selectedNode?: Node;
  selectedEdge?: Edge;
  nodes: Node[];
  edges: Edge[];
  tfPreview: TofuGenerationResult | null;
  kubernetesPreview: KubernetesYamlGenerationResult | null;
  kubernetesValidation: KubernetesValidationResult | null;
  tofuPlan: TofuPlanResult | null;
  planDeployment: PlanDeployment | null;
  deploymentHistory: DeploymentSummaryItem[];
  iacPanelOpen: boolean;
  awsPanelOpen: boolean;
  kubernetesPanelOpen: boolean;
  inspectorOpen: boolean;
  runPanelOpen: boolean;
  sidePanelsCollapsed: boolean;
  feedbackPanelOpen: boolean;
  inspectorBottomInset: string;
  inspectorWidth: number;
  runPanelHeightVh: number;
  awsVerified: boolean;
  feedbackLoading: boolean;
  hasFeedback: boolean;
  isStale: boolean;
  autoReflect: boolean;
  generating: boolean;
  planning: boolean;
  applying: boolean;
  destroying: boolean;
  actionDisabled: boolean;
  hiddenCount: number;
  showHidden: boolean;
  containedNodeCount: number;
  showContainmentBadges: boolean;
  securityGroupOptions: SecurityGroupOption[];
  onInspectorToggle: () => void;
  onRunPanelToggle: () => void;
  onSidePanelsToggle: () => void;
  onInspectorWidthChange: (width: number) => void;
  onRunPanelHeightChange: (height: number) => void;
  onAwsToggle: () => void;
  onKubernetesToggle: () => void;
  onFeedbackOpen: () => void;
  onIacOpen: () => void;
  onGenerateTofu: () => void;
  onGenerateKubernetesYaml: () => void;
  onRunPlan: () => void;
  onApplyPlan: () => void;
  onDestroyPlan?: () => void;
  onDestroyApply?: () => void;
  onToggleShowHidden: () => void;
  onToggleContainmentBadges: () => void;
  onNodeChange: (nodeId: string, updates: NodeUpdate) => void;
  onNodeClose: () => void;
  onToggleHidden: (nodeId: string, hidden: boolean) => void;
  onSecurityGroupToggle: (
    resourceId: string,
    securityGroupId: string,
    attached: boolean,
  ) => void;
  onSecurityGroupCreate: (resourceId: string) => void;
  onSecurityGroupSelect: (securityGroupId: string) => void;
  onEdgeChange: (edgeId: string, updates: EdgeUpdate) => void;
  onEdgeClose: () => void;
  onTfClose: () => void;
  onTfDownload: () => void;
  onKubernetesYamlClose: () => void;
  onKubernetesYamlDownload: () => void;
  onPlanClose: () => void;
  onAwsClose: () => void;
  onKubernetesClose: () => void;
  onAwsUpdated: (awsAccount: AwsAccount) => void;
  onKubernetesNodeSelect: (nodeId: string) => void;
};

export function CanvasSidePanels({
  canvasId,
  canvasKind = "aws",
  canvasState = "design",
  awsAccount,
  selectedNode,
  selectedEdge,
  nodes,
  edges,
  tfPreview,
  kubernetesPreview,
  kubernetesValidation,
  tofuPlan,
  planDeployment,
  deploymentHistory,
  iacPanelOpen,
  awsPanelOpen,
  kubernetesPanelOpen,
  inspectorOpen,
  runPanelOpen,
  sidePanelsCollapsed,
  feedbackPanelOpen,
  inspectorBottomInset,
  inspectorWidth,
  runPanelHeightVh,
  awsVerified,
  feedbackLoading,
  hasFeedback,
  isStale,
  autoReflect,
  generating,
  planning,
  applying,
  destroying,
  actionDisabled,
  hiddenCount,
  showHidden,
  containedNodeCount,
  showContainmentBadges,
  securityGroupOptions,
  onInspectorToggle,
  onRunPanelToggle,
  onSidePanelsToggle,
  onInspectorWidthChange,
  onRunPanelHeightChange,
  onAwsToggle,
  onKubernetesToggle,
  onFeedbackOpen,
  onIacOpen,
  onGenerateTofu,
  onGenerateKubernetesYaml,
  onRunPlan,
  onApplyPlan,
  onDestroyPlan,
  onDestroyApply,
  onToggleShowHidden,
  onToggleContainmentBadges,
  onNodeChange,
  onNodeClose,
  onToggleHidden,
  onSecurityGroupToggle,
  onSecurityGroupCreate,
  onSecurityGroupSelect,
  onEdgeChange,
  onEdgeClose,
  onTfClose,
  onTfDownload,
  onKubernetesYamlClose,
  onKubernetesYamlDownload,
  onPlanClose,
  onAwsClose,
  onKubernetesClose,
  onAwsUpdated,
  onKubernetesNodeSelect,
}: CanvasSidePanelsProps) {
  const hasInspectorContent = Boolean(
    selectedNode || selectedEdge || awsPanelOpen || kubernetesPanelOpen,
  );
  const hasRunContent = Boolean(
    iacPanelOpen ||
      tfPreview ||
      kubernetesPreview ||
      tofuPlan ||
      planDeployment ||
      deploymentHistory.length > 0,
  );
  const canApply =
    planDeployment?.mode !== "destroy" &&
    Boolean(tofuPlan?.ok) &&
    (planDeployment?.status === "success" ||
      planDeployment?.status === "approved") &&
    Boolean(planDeployment?.plan_artifact) &&
    Boolean(planDeployment?.state_backend);
  const hasAppliedResources =
    canvasState === "applied" || canvasState === "running" || canvasState === "deploy";
  const isDestroyPlan = planDeployment?.mode === "destroy";
  const canRunDestroyPlan =
    hasAppliedResources && !isDestroyPlan && Boolean(onDestroyPlan);
  const canApplyDestroy =
    isDestroyPlan &&
    Boolean(tofuPlan?.ok) &&
    (planDeployment?.status === "success" ||
      planDeployment?.status === "approved") &&
    Boolean(planDeployment?.plan_artifact) &&
    Boolean(planDeployment?.state_backend) &&
    Boolean(onDestroyApply);
  const isKubernetesCanvas = canvasKind === "kubernetes";
  const isAwsCanvas = !isKubernetesCanvas;
  const inspectorDragRef = useRef<{ x: number; width: number } | null>(null);
  const runPanelDragRef = useRef<{ y: number; height: number } | null>(null);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      if (inspectorDragRef.current) {
        const delta = inspectorDragRef.current.x - event.clientX;
        const next = inspectorDragRef.current.width + delta;
        onInspectorWidthChange(Math.max(300, Math.min(560, next)));
      }
      if (runPanelDragRef.current) {
        const deltaPx = runPanelDragRef.current.y - event.clientY;
        const deltaVh = (deltaPx / window.innerHeight) * 100;
        const next = runPanelDragRef.current.height + deltaVh;
        onRunPanelHeightChange(Math.max(24, Math.min(72, next)));
      }
    };
    const onUp = () => {
      inspectorDragRef.current = null;
      runPanelDragRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [onInspectorWidthChange, onRunPanelHeightChange]);

  const onInspectorResizeStart = (event: ReactMouseEvent) => {
    event.preventDefault();
    inspectorDragRef.current = { x: event.clientX, width: inspectorWidth };
    document.body.style.cursor = "ew-resize";
    document.body.style.userSelect = "none";
  };

  const onRunPanelResizeStart = (event: ReactMouseEvent) => {
    event.preventDefault();
    runPanelDragRef.current = { y: event.clientY, height: runPanelHeightVh };
    document.body.style.cursor = "ns-resize";
    document.body.style.userSelect = "none";
  };

  if (sidePanelsCollapsed) {
    return (
      <button
        onClick={onSidePanelsToggle}
        title="우측 패널 열기"
        className="absolute right-0 top-20 z-[10] flex h-32 w-12 items-center justify-center rounded-l-lg border border-r-0 border-[var(--color-border)] bg-[var(--color-surface)] text-[11px] font-semibold tracking-wider text-[var(--color-text-muted)] shadow-[var(--shadow-md)] [writing-mode:vertical-rl] hover:w-14 hover:text-[var(--color-accent)]"
      >
        패널
      </button>
    );
  }

  return (
    <>
      <div
        className="absolute right-0 top-0 z-[9] flex pointer-events-none"
        style={{ bottom: inspectorBottomInset }}
      >
        {!inspectorOpen && (
          <button
            onClick={onInspectorToggle}
            title="Inspector 열기"
            className="pointer-events-auto mt-20 h-28 rounded-l-md border border-r-0 border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)] shadow-[var(--shadow-sm)] [writing-mode:vertical-rl] hover:text-[var(--color-accent)]"
          >
            Inspector
          </button>
        )}
        {inspectorOpen && (
          <aside
            className="pointer-events-auto relative flex h-full flex-col border-l border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-lg)]"
            style={{ width: `min(${inspectorWidth}px, calc(100vw - 5rem))` }}
          >
            <div
              onMouseDown={onInspectorResizeStart}
              title="드래그하여 Inspector 폭 조절"
              className="absolute inset-y-0 left-0 z-10 w-1.5 cursor-ew-resize hover:bg-[var(--color-accent)]/30"
            />
            <div className="flex h-11 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3">
              <strong className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                Inspector
              </strong>
              <div className="flex items-center gap-1">
                <button
                  onClick={onSidePanelsToggle}
                  title="우측 패널 전체 접기"
                  className="rounded px-2 py-1 text-xs text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
                >
                  접기
                </button>
                <button
                  onClick={onInspectorToggle}
                  title="Inspector 닫기"
                  className="rounded px-2 py-1 text-sm text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
                >
                  ›
                </button>
              </div>
            </div>
            <div className="shrink-0 border-b border-[var(--color-border)]">
              <InspectorControls
                showAwsAction={canvasKind !== "kubernetes"}
                awsVerified={awsVerified}
                feedbackLoading={feedbackLoading}
                hasFeedback={hasFeedback}
                isStale={isStale}
                autoReflect={autoReflect}
                hiddenCount={hiddenCount}
                showHidden={showHidden}
                containedNodeCount={containedNodeCount}
                showContainmentBadges={showContainmentBadges}
                onAwsToggle={onAwsToggle}
                onKubernetesToggle={onKubernetesToggle}
                onFeedbackOpen={onFeedbackOpen}
                onIacOpen={onIacOpen}
                onToggleShowHidden={onToggleShowHidden}
                onToggleContainmentBadges={onToggleContainmentBadges}
              />
            </div>
            <InspectorSelectionHeader
              awsPanelOpen={awsPanelOpen}
              kubernetesPanelOpen={kubernetesPanelOpen}
              selectedNode={selectedNode}
              selectedEdge={selectedEdge}
            />
            <div className="min-h-0 flex-1 overflow-y-auto bg-[var(--color-surface)]">
              {kubernetesPanelOpen ? (
                <KubernetesResourceTree
                  nodes={nodes}
                  edges={edges}
                  onClose={onKubernetesClose}
                  onSelectNode={onKubernetesNodeSelect}
                />
              ) : awsPanelOpen && canvasId ? (
                <AwsAccountPanel
                  canvasId={canvasId}
                  awsAccount={awsAccount}
                  onClose={onAwsClose}
                  onUpdated={onAwsUpdated}
                />
              ) : selectedNode ? (
                <PropertiesPanel
                  node={selectedNode}
                  onChange={onNodeChange}
                  onClose={onNodeClose}
                  onToggleHidden={onToggleHidden}
                  securityGroupOptions={securityGroupOptions}
                  onSecurityGroupToggle={onSecurityGroupToggle}
                  onSecurityGroupCreate={onSecurityGroupCreate}
                  onSecurityGroupSelect={onSecurityGroupSelect}
                />
              ) : selectedEdge ? (
                <EdgePropertiesPanel
                  edge={selectedEdge}
                  onChange={onEdgeChange}
                  onClose={onEdgeClose}
                />
              ) : (
                <div className="p-5 text-sm leading-relaxed text-[var(--color-text-muted)]">
                  캔버스에서 리소스나 연결선을 선택하면 속성이 표시됩니다.
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {hasRunContent && !feedbackPanelOpen && (
        <div
          className={
            runPanelOpen
              ? "absolute inset-x-0 bottom-0 z-[8] flex flex-col border-t border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-lg)]"
              : "absolute bottom-3 left-1/2 z-[8] -translate-x-1/2"
          }
          style={runPanelOpen ? { height: `${runPanelHeightVh}vh` } : undefined}
        >
          {!runPanelOpen ? (
            <button
              onClick={onRunPanelToggle}
              className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text)] shadow-[var(--shadow-md)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            >
              Run Panel 열기
            </button>
          ) : (
            <>
              <div
                onMouseDown={onRunPanelResizeStart}
                title="드래그하여 Run Panel 높이 조절"
                className="h-1.5 shrink-0 cursor-ns-resize border-t-2 border-[var(--color-border)] transition-colors hover:border-[var(--color-accent)]"
              />
              <div className="flex h-10 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  <span>Run Panel</span>
                  {tfPreview && <span className="rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[var(--color-accent)]">Tofu</span>}
                  {kubernetesPreview && <span className="rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[var(--color-accent)]">YAML</span>}
                  {(tofuPlan || planDeployment) && <span className="rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[var(--color-accent)]">Plan</span>}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={onSidePanelsToggle}
                    title="우측 패널 전체 접기"
                    className="rounded px-2 py-1 text-xs text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
                  >
                    접기
                  </button>
                  <button
                    onClick={onRunPanelToggle}
                    title="Run Panel 접기"
                    className="rounded px-2 py-1 text-sm text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
                  >
                    ˅
                  </button>
                </div>
              </div>
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="flex h-11 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-3">
                  <div className="text-xs font-semibold text-[var(--color-text)]">
                    IaC
                  </div>
                  <div className="flex min-w-0 flex-wrap items-center justify-end gap-2 overflow-x-auto">
                    {isAwsCanvas && (
                      <>
                        <button
                          onClick={onGenerateTofu}
                          disabled={generating || actionDisabled}
                          className={
                            generating || actionDisabled
                              ? "cursor-not-allowed whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-1.5 text-xs text-[var(--color-text-subtle)]"
                              : "whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                          }
                        >
                          {generating ? "생성 중" : ".tf 생성"}
                        </button>
                        <button
                          onClick={onRunPlan}
                          disabled={planning || actionDisabled}
                          className={
                            planning || actionDisabled
                              ? "cursor-not-allowed whitespace-nowrap rounded-md bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-subtle)]"
                              : "whitespace-nowrap rounded-md bg-[var(--color-accent)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
                          }
                        >
                          {planning ? "Planning" : "Plan"}
                        </button>
                        <button
                          onClick={isDestroyPlan ? onDestroyApply : onApplyPlan}
                          disabled={
                            !(isDestroyPlan ? canApplyDestroy : canApply) ||
                            applying ||
                            destroying
                          }
                          title={
                            isDestroyPlan
                              ? canApplyDestroy
                                ? "승인된 Destroy Plan artifact로 Destroy 실행"
                                : "먼저 Destroy Plan을 생성하고 승인해야 합니다."
                              : canApply
                                ? "승인된 Plan artifact로 Apply 실행"
                              : "먼저 Apply-ready Plan을 생성하고 승인해야 합니다."
                          }
                          className={
                            (!(isDestroyPlan ? canApplyDestroy : canApply) ||
                              applying ||
                              destroying)
                              ? "cursor-not-allowed whitespace-nowrap rounded-md bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-subtle)]"
                              : isDestroyPlan
                                ? "whitespace-nowrap rounded-md bg-[var(--color-danger)] px-2.5 py-1.5 text-xs font-medium text-white hover:brightness-95"
                                : "whitespace-nowrap rounded-md bg-[var(--color-success)] px-2.5 py-1.5 text-xs font-medium text-white hover:brightness-95"
                          }
                        >
                          {destroying
                            ? "Destroying"
                            : applying
                              ? "Applying"
                              : isDestroyPlan
                                ? "Confirm Destroy"
                                : "Apply"}
                        </button>
                        <button
                          onClick={onDestroyPlan}
                          disabled={!canRunDestroyPlan || planning || destroying}
                          title={
                            canRunDestroyPlan
                              ? "관리 리소스 삭제를 위한 Destroy Plan 실행"
                              : hasAppliedResources
                                ? "Destroy pipeline은 아직 구현되지 않았습니다."
                                : "적용된 리소스가 있을 때 사용할 수 있습니다."
                          }
                          className={
                            canRunDestroyPlan && !planning && !destroying
                              ? "whitespace-nowrap rounded-md border border-[var(--color-danger)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                              : "cursor-not-allowed whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text-subtle)]"
                          }
                        >
                          {planning && isDestroyPlan ? "Destroy Plan..." : "Destroy"}
                        </button>
                      </>
                    )}
                    {isKubernetesCanvas && (
                      <>
                        <button
                          onClick={onGenerateKubernetesYaml}
                          disabled={generating || actionDisabled}
                          className={
                            generating || actionDisabled
                              ? "cursor-not-allowed whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-1.5 text-xs text-[var(--color-text-subtle)]"
                              : "whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
                          }
                        >
                          {generating ? "검증 중" : "YAML + 검증"}
                        </button>
                        <button
                          disabled
                          title="Cluster-side dry-run은 Kubernetes Target credential 연결 후 활성화됩니다."
                          className="cursor-not-allowed whitespace-nowrap rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-1.5 text-xs text-[var(--color-text-subtle)]"
                        >
                          Dry-run 준비중
                        </button>
                      </>
                    )}
                  </div>
                </div>
                <div className="min-h-0 flex-1">
                  {(tofuPlan || planDeployment) ? (
                    <TofuPlanPanel
                      result={tofuPlan}
                      mode={planDeployment?.mode || null}
                      status={planDeployment?.status || tofuPlan?.deployment_status || null}
                      progressEvents={planDeployment?.progress_events || []}
                      deploymentId={planDeployment?.id || tofuPlan?.deployment_id || null}
                      assumedArn={planDeployment?.assumed_arn || tofuPlan?.assumed_arn || null}
                      onClose={onPlanClose}
                      embedded
                    />
                  ) : kubernetesPreview ? (
                    <div className="flex h-full min-h-0 flex-col">
                      {kubernetesValidation && (
                        <KubernetesValidationSummary
                          result={kubernetesValidation}
                        />
                      )}
                      <div className="min-h-0 flex-1">
                        <TfPreviewPanel
                          tf={kubernetesPreview.yaml}
                          filename={kubernetesPreview.filename}
                          title="Kubernetes YAML 미리보기"
                          downloadLabel="YAML 다운로드"
                          onClose={onKubernetesYamlClose}
                          onDownload={onKubernetesYamlDownload}
                          embedded
                        />
                      </div>
                    </div>
                  ) : tfPreview ? (
                    <TfPreviewPanel
                      tf={tfPreview.tf}
                      filename={tfPreview.filename}
                      onClose={onTfClose}
                      onDownload={onTfDownload}
                      embedded
                    />
                  ) : (
                    <RunHistoryList items={deploymentHistory} />
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}

function RunHistoryList({ items }: { items: DeploymentSummaryItem[] }) {
  if (items.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-[var(--color-text-muted)]">
        대기 중
      </div>
    );
  }
  return (
    <div className="h-full overflow-auto p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-semibold text-[var(--color-text)]">
          최근 실행
        </div>
        <div className="text-[10px] uppercase text-[var(--color-text-subtle)]">
          Plan / Apply / Destroy
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {items.slice(0, 8).map((item) => (
          <div
            key={item.id}
            className="rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="text-xs font-medium text-[var(--color-text)]">
                {item.mode}
              </div>
              <span className={runStatusClass(item.status)}>
                {item.status}
              </span>
            </div>
            <div className="mt-1 truncate text-[11px] text-[var(--color-text-subtle)]">
              {item.created_at
                ? new Date(item.created_at).toLocaleString("ko-KR")
                : item.id}
            </div>
            {item.error_message && (
              <div className="mt-1 truncate text-[11px] text-[var(--color-danger)]">
                {item.error_message}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function runStatusClass(status: string) {
  if (status === "applied" || status === "destroyed") {
    return "rounded bg-[var(--color-success)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-success)]";
  }
  if (status === "failed") {
    return "rounded bg-[var(--color-danger)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-danger)]";
  }
  if (status === "queued" || status === "planning" || status === "applying" || status === "destroying") {
    return "rounded bg-[var(--color-warning)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-warning)]";
  }
  return "rounded bg-[var(--color-bg-subtle)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-text-muted)]";
}
