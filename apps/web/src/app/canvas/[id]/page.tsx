"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  ReactFlowProvider,
  useReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type OnReconnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  generateKubernetesYaml,
  generateTofu,
  getCanvas,
  getCanvasDeploymentHistory,
  insertCanvasFragment,
  listCanvasFragments,
  updateCanvas,
  validateKubernetesCanvas,
  type AwsAccount,
  type Canvas,
  type CanvasFragment,
  type DeploymentSummaryItem,
  type KubernetesValidationResult,
  type KubernetesYamlGenerationResult,
  type TofuGenerationResult,
  type ValidationIssue,
} from "@/lib/api";
import { usePlanRunner } from "@/hooks/usePlanRunner";
import { useFeedbackRunner } from "@/hooks/useFeedbackRunner";
import { PaletteSidebar } from "@/components/PaletteSidebar";
import { FeedbackPanel } from "@/components/FeedbackPanel";
import { CanvasToolbar } from "@/components/canvas/CanvasToolbar";
import { CanvasSidePanels } from "@/components/canvas/CanvasSidePanels";
import { CanvasFlowStage } from "@/components/canvas/CanvasFlowStage";
import { KubernetesResourceMapStage } from "@/components/canvas/KubernetesResourceMapStage";
import { CanvasStatusView } from "@/components/canvas/CanvasStatusView";
import { NodeDensityProvider } from "@/lib/node-density-context";
import { getNodeTypeDef } from "@/lib/node-types";
import { getGroupTypeDef } from "@/lib/group-types";
import {
  assignParentGroups,
  findMagneticAlignment,
  getAlignmentCandidates,
  getContainment,
  getDescendantIds,
  snapPosition,
  type AlignmentGuides,
  type ContainmentItem,
} from "@/lib/canvas-graph";
import { canvasGraphToFlow, flowToCanvasGraph } from "@/lib/canvas-serialization";
import { getEdgeAnimated, getEdgeStyle, type EdgeKind } from "@/lib/edge-types";
import { inferEdgeKind } from "@/lib/edge-inference";

type DragSnapshot = {
  positions: Map<string, { x: number; y: number }>;
};

type GraphSnapshot = {
  nodes: Node[];
  edges: Edge[];
};

type SaveStatus = "saved" | "dirty" | "saving" | "error";

type ClipboardSnapshot = GraphSnapshot;

type CanvasNotice = {
  id: number;
  message: string;
  tone: "success" | "error" | "info";
};

type SlotSecurityGroup = {
  id: string;
  name: string;
};

const SECURITY_GROUP_TYPE = "aws.ec2.security_group";

function nodeDisplayName(node: Node | undefined): string {
  if (!node) return "";
  return (
    (node.data?.display_name as string | undefined) ||
    getNodeTypeDef(node.type || "")?.displayName ||
    node.id
  );
}

function cloneGraphSnapshot(snapshot: GraphSnapshot): GraphSnapshot {
  return {
    nodes: snapshot.nodes.map((node) => ({
      ...node,
      position: { ...node.position },
      data: clonePlainObject(node.data),
      style: clonePlainObject(node.style),
    })),
    edges: snapshot.edges.map((edge) => ({
      ...edge,
      data: clonePlainObject(edge.data),
      style: clonePlainObject(edge.style),
    })),
  };
}

function clonePlainObject<T>(value: T): T {
  if (value == null) return value;
  return JSON.parse(JSON.stringify(value)) as T;
}

function graphFingerprint(nodes: Node[], edges: Edge[]): string {
  return JSON.stringify(flowToCanvasGraph(nodes, edges));
}

function isEditableKeyTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    tag === "input" ||
    tag === "textarea" ||
    tag === "select"
  );
}

function hasBrowserTextSelection(): boolean {
  const selection = window.getSelection();
  return Boolean(selection && selection.toString().length > 0);
}

function isAssociationEdgeForSlot(edge: Edge, slotType: string): boolean {
  const def = getNodeTypeDef(slotType);
  const edgeTypes = def?.association?.edgeTypes || ["network", "reference"];
  return edgeTypes.includes((edge.type || "network") as EdgeKind);
}

function canAttachSlotTo(slotType: string, targetType: string | undefined): boolean {
  if (!targetType) return false;
  const attachableTo = getNodeTypeDef(slotType)?.association?.attachableTo || [];
  return attachableTo.includes(targetType);
}

function nearestAncestorIdOfType(
  node: Node | undefined,
  nodeById: Map<string, Node>,
  nodeType: string,
): string | null {
  const seen = new Set<string>();
  let currentId = node?.data?.parent_group_id as string | null | undefined;
  while (currentId && !seen.has(currentId)) {
    seen.add(currentId);
    const current = nodeById.get(currentId);
    if (!current) return null;
    if (current.type === nodeType) return current.id;
    currentId = current.data?.parent_group_id as string | null | undefined;
  }
  return null;
}

function securityGroupAttachment(
  edge: Edge,
  nodeById: Map<string, Node>,
): { resourceId: string; sg: SlotSecurityGroup; sgId: string } | null {
  if (!isAssociationEdgeForSlot(edge, SECURITY_GROUP_TYPE)) return null;

  const source = nodeById.get(edge.source);
  const target = nodeById.get(edge.target);
  if (!source || !target) return null;

  if (
    source.type === SECURITY_GROUP_TYPE &&
    canAttachSlotTo(SECURITY_GROUP_TYPE, target.type)
  ) {
    return {
      resourceId: target.id,
      sgId: source.id,
      sg: { id: source.id, name: nodeDisplayName(source) },
    };
  }

  if (
    target.type === SECURITY_GROUP_TYPE &&
    canAttachSlotTo(SECURITY_GROUP_TYPE, source.type)
  ) {
    return {
      resourceId: source.id,
      sgId: target.id,
      sg: { id: target.id, name: nodeDisplayName(target) },
    };
  }

  return null;
}

function CanvasInner() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const { flowToScreenPosition, screenToFlowPosition } = useReactFlow();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  const [canvas, setCanvas] = useState<Canvas | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("saved");
  const [autoSaveEnabled, setAutoSaveEnabled] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  // 숨긴 리소스 표시 토글 (헤더 버튼). 기본은 가림.
  const [showHidden, setShowHidden] = useState(false);
  const [showSecurityDetails, setShowSecurityDetails] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(true);
  const [fragments, setFragments] = useState<CanvasFragment[]>([]);
  const [insertingFragment, setInsertingFragment] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [runPanelOpen, setRunPanelOpen] = useState(true);
  const [sidePanelsCollapsed, setSidePanelsCollapsed] = useState(false);
  const [iacPanelOpen, setIacPanelOpen] = useState(false);
  const [kubernetesPanelOpen, setKubernetesPanelOpen] = useState(false);
  const [inspectorWidth, setInspectorWidth] = useState(344);
  const [runPanelHeightVh, setRunPanelHeightVh] = useState(42);
  const [feedbackPanelHeightVh, setFeedbackPanelHeightVh] = useState(40);
  const [notice, setNotice] = useState<CanvasNotice | null>(null);

  const [tfPreview, setTfPreview] = useState<TofuGenerationResult | null>(null);
  const [kubernetesPreview, setKubernetesPreview] =
    useState<KubernetesYamlGenerationResult | null>(null);
  const [kubernetesValidation, setKubernetesValidation] =
    useState<KubernetesValidationResult | null>(null);
  const [deploymentHistory, setDeploymentHistory] = useState<
    DeploymentSummaryItem[]
  >([]);
  const [awsPanelOpen, setAwsPanelOpen] = useState(false);

  const [editingName, setEditingName] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [alignmentGuides, setAlignmentGuides] = useState<AlignmentGuides>({});
  const [showContainmentBadges, setShowContainmentBadges] = useState(true);
  const dragSnapshotRef = useRef<DragSnapshot | null>(null);
  const lastDeploymentNoticeRef = useRef<string | null>(null);
  const savedFingerprintRef = useRef("");
  const latestSnapshotRef = useRef<GraphSnapshot>({ nodes: [], edges: [] });
  const historyCursorRef = useRef(0);
  const historyRef = useRef<GraphSnapshot[]>([]);
  const nodeDragInProgressRef = useRef(false);
  const restoringHistoryRef = useRef(false);
  const clipboardRef = useRef<ClipboardSnapshot | null>(null);

  const showNotice = useCallback(
    (message: string, tone: CanvasNotice["tone"] = "info") => {
      setNotice({ id: Date.now(), message, tone });
    },
    [],
  );
  const loadCanvasState = useCallback((c: Canvas) => {
    setCanvas(c);
    const flow = canvasGraphToFlow(c.graph);
    const initialNodes = assignParentGroups(flow.nodes);
    const snapshot = cloneGraphSnapshot({
      nodes: initialNodes,
      edges: flow.edges,
    });
    const fingerprint = graphFingerprint(snapshot.nodes, snapshot.edges);
    savedFingerprintRef.current = fingerprint;
    latestSnapshotRef.current = snapshot;
    historyRef.current = [cloneGraphSnapshot(snapshot)];
    historyCursorRef.current = 0;
    setSaveStatus("saved");
    setNodes(initialNodes);
    setEdges(flow.edges);
    setLoaded(true);
  }, []);
  const handlePlanError = useCallback((message: string) => {
    showNotice(message, "error");
  }, [showNotice]);
  const refreshDeploymentHistory = useCallback(() => {
    if (!id) return;
    getCanvasDeploymentHistory(id, 12)
      .then((history) => setDeploymentHistory(history.items))
      .catch(() => setDeploymentHistory([]));
  }, [id]);
  const resetPlanPanels = useCallback(() => {
    setTfPreview(null);
    setKubernetesPreview(null);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setFeedbackOpen(false);
    setIacPanelOpen(true);
    setRunPanelOpen(true);
    setSidePanelsCollapsed(false);
  }, []);
  const {
    planning,
    applying,
    destroying,
    tofuPlan,
    setTofuPlan,
    planDeployment,
    setPlanDeployment,
    runPlan: handleRunPlan,
    approveAndApply: handleApproveAndApply,
    runDestroyPlan: handleRunDestroyPlan,
    approveAndDestroy: handleApproveAndDestroy,
  } = usePlanRunner({
    canvasId: id,
    onBeforeRun: resetPlanPanels,
    onError: handlePlanError,
  });

  const selectedEdge = edges.find((e) => e.id === selectedEdgeId);

  const handleEdgeStepPositionChange = useCallback(
    (edgeId: string, stepPosition: number) => {
      setEdges((eds) =>
        eds.map((edge) =>
          edge.id === edgeId
            ? {
                ...edge,
                data: {
                  ...(edge.data || {}),
                  pathStepPosition: stepPosition,
                },
              }
            : edge,
        ),
      );
    },
    [],
  );

  // 캔버스 변경 감지용 fingerprint — 분석 시점 캡처와 비교
  const canvasFingerprint = useMemo(() => {
    return JSON.stringify({
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type,
        x: Math.round(n.position.x),
        y: Math.round(n.position.y),
        data: n.data,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        s: e.source,
        t: e.target,
        type: e.type,
      })),
    });
  }, [nodes, edges]);

  const handleFeedbackNodeSelect = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
  }, []);
  const {
    feedback,
    feedbackLoading,
    feedbackError,
    feedbackOpen,
    setFeedbackOpen,
    streamingText,
    isStale,
    autoReflect,
    setAutoReflect,
    requestFeedback: handleRequestFeedback,
    stopFeedback: handleStopFeedback,
    openFeedbackPanel: handleOpenFeedbackPanel,
    handleFeedbackItemClick,
  } = useFeedbackRunner({
    canvasId: id,
    canvasFingerprint,
    onSelectNode: handleFeedbackNodeSelect,
  });

  const handleFeedbackOpenFromToolbar = useCallback(() => {
    if (feedbackOpen) {
      setFeedbackOpen(false);
      return;
    }
    setRunPanelOpen(false);
    setIacPanelOpen(false);
    handleOpenFeedbackPanel();
  }, [feedbackOpen, handleOpenFeedbackPanel, setFeedbackOpen]);

  const handleIacOpenFromToolbar = useCallback(() => {
    if (iacPanelOpen && runPanelOpen) {
      setIacPanelOpen(false);
      setRunPanelOpen(false);
      return;
    }
    setFeedbackOpen(false);
    setIacPanelOpen(true);
    setRunPanelOpen(true);
    setSidePanelsCollapsed(false);
  }, [iacPanelOpen, runPanelOpen, setFeedbackOpen]);

  const handleKubernetesOpenFromInspector = useCallback(() => {
    setInspectorOpen(true);
    setSidePanelsCollapsed(false);
    setAwsPanelOpen(false);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setKubernetesPanelOpen((value) => !value);
  }, []);

  const handleKubernetesNodeSelect = useCallback((nodeId: string) => {
    setKubernetesPanelOpen(false);
    setAwsPanelOpen(false);
    setSelectedEdgeId(null);
    setSelectedNodeId(nodeId);
    setInspectorOpen(true);
    setSidePanelsCollapsed(false);
  }, []);

  const inspectorBottomInset = useMemo(() => {
    const hasRunContent = Boolean(
      iacPanelOpen || tfPreview || kubernetesPreview || tofuPlan || planDeployment,
    );
    if (feedbackOpen) return `${feedbackPanelHeightVh}vh`;
    if (hasRunContent && runPanelOpen) return `${runPanelHeightVh}vh`;
    return "0px";
  }, [
    feedbackOpen,
    feedbackPanelHeightVh,
    iacPanelOpen,
    kubernetesPreview,
    planDeployment,
    runPanelHeightVh,
    runPanelOpen,
    tfPreview,
    tofuPlan,
  ]);
  const resourceMapRightInsetPx =
    sidePanelsCollapsed || !inspectorOpen ? 0 : inspectorWidth;

  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 4200);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    if (!planDeployment) return;
    const key = `${planDeployment.id}:${planDeployment.status}`;
    if (lastDeploymentNoticeRef.current === key) return;
    lastDeploymentNoticeRef.current = key;

    if (planDeployment.status === "success") {
      showNotice("Plan이 완료되었습니다.", "success");
    } else if (planDeployment.status === "approved") {
      showNotice("Plan이 승인되었습니다.", "success");
    } else if (planDeployment.status === "applying") {
      showNotice("Apply 실행을 시작했습니다.", "info");
    } else if (planDeployment.status === "applied") {
      setCanvas((current) =>
        current ? { ...current, state: "applied" } : current,
      );
      showNotice("Apply가 완료되었습니다.", "success");
    } else if (planDeployment.status === "destroying") {
      showNotice("Destroy 실행을 시작했습니다.", "info");
    } else if (planDeployment.status === "destroyed") {
      setCanvas((current) =>
        current ? { ...current, state: "destroyed" } : current,
      );
      showNotice("Destroy가 완료되었습니다.", "success");
    } else if (planDeployment.status === "failed") {
      showNotice(planDeployment.error_message || "실행이 실패했습니다.", "error");
    }
  }, [planDeployment, showNotice]);

  // 숨김 처리된 노드 id 집합
  const hiddenIds = useMemo(
    () => new Set(nodes.filter((n) => n.data?.hidden).map((n) => n.id)),
    [nodes],
  );

  // parent_group_id 체인 표시용 index
  const nodeById = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes],
  );

  const securitySlotModel = useMemo(() => {
    const groupsByResource = new Map<string, SlotSecurityGroup[]>();
    const attachedSgIds = new Set<string>();
    const attachmentEdgeIds = new Set<string>();

    for (const edge of edges) {
      const attachment = securityGroupAttachment(edge, nodeById);
      if (!attachment) continue;
      attachmentEdgeIds.add(edge.id);
      attachedSgIds.add(attachment.sgId);
      const list = groupsByResource.get(attachment.resourceId) || [];
      if (!list.some((group) => group.id === attachment.sg.id)) {
        list.push(attachment.sg);
      }
      groupsByResource.set(attachment.resourceId, list);
    }

    return { groupsByResource, attachedSgIds, attachmentEdgeIds };
  }, [edges, nodeById]);

  const securityGroupOptions = useMemo<SlotSecurityGroup[]>(
    () =>
      nodes
        .filter((node) => node.type === SECURITY_GROUP_TYPE)
        .map((node) => ({
          id: node.id,
          name: nodeDisplayName(node),
        })),
    [nodes],
  );

  const validationIssuesByNodeId = useMemo(() => {
    const map = new Map<string, ValidationIssue[]>();
    for (const issue of tofuPlan?.validation_issues || []) {
      if (!issue.node_id) continue;
      const list = map.get(issue.node_id) || [];
      list.push(issue);
      map.set(issue.node_id, list);
    }
    return map;
  }, [tofuPlan?.validation_issues]);

  // 노드/그룹 공통 포함 목록 — 가장 작은 영역부터 바깥 영역 순.
  const nodesWithContainment = useMemo<Node[]>(
    () =>
      nodes.map((n) => ({
        ...n,
        data: {
          ...n.data,
          containment: getContainment(n, nodeById),
          showContainmentBadge: showContainmentBadges,
          validationIssues: validationIssuesByNodeId.get(n.id) || [],
          securityGroups: securitySlotModel.groupsByResource.get(n.id) || [],
        },
      })),
    [
      nodes,
      nodeById,
      securitySlotModel.groupsByResource,
      showContainmentBadges,
      validationIssuesByNodeId,
    ],
  );

  const selectedNode = nodesWithContainment.find((n) => n.id === selectedNodeId);

  useEffect(() => {
    if (
      !showSecurityDetails &&
      selectedNodeId &&
      securitySlotModel.attachedSgIds.has(selectedNodeId)
    ) {
      setSelectedNodeId(null);
    }
    if (
      !showSecurityDetails &&
      selectedEdgeId &&
      securitySlotModel.attachmentEdgeIds.has(selectedEdgeId)
    ) {
      setSelectedEdgeId(null);
    }
  }, [
    securitySlotModel.attachedSgIds,
    securitySlotModel.attachmentEdgeIds,
    selectedEdgeId,
    selectedNodeId,
    showSecurityDetails,
  ]);

  const containedNodeCount = useMemo(
    () =>
      nodesWithContainment.filter(
        (n) => ((n.data?.containment as ContainmentItem[] | undefined) || []).length > 0,
      ).length,
    [nodesWithContainment],
  );

  // 화면용 노드 — 숨김 필터 + 숨김(보기 모드) 흐림 + 그룹 소속 배지 주입.
  const displayNodes = useMemo(() => {
    const base = showHidden
      ? nodesWithContainment
      : nodesWithContainment.filter((n) => !n.data?.hidden);
    return base.map((n) => {
      let next = n;
      if (
        !showSecurityDetails &&
        n.type === SECURITY_GROUP_TYPE
      ) {
        next = { ...next, hidden: true };
      }
      if (n.data?.hidden) {
        next = { ...next, style: { ...(next.style || {}), opacity: 0.4 } };
      }
      return next;
    });
  }, [
    nodesWithContainment,
    showHidden,
    showSecurityDetails,
  ]);

  // 화면용 엣지 — 꺾은 직선(smoothstep) + 숨김 노드 연결 필터/흐림.
  const displayEdges = useMemo(
    () =>
      edges
        .filter(
          (e) =>
            (showSecurityDetails ||
              (nodeById.get(e.source)?.type !== SECURITY_GROUP_TYPE &&
                nodeById.get(e.target)?.type !== SECURITY_GROUP_TYPE)) &&
            (showHidden ||
              (!hiddenIds.has(e.source) && !hiddenIds.has(e.target))),
        )
        .map((e) => {
          const dim = hiddenIds.has(e.source) || hiddenIds.has(e.target);
          const selected = e.id === selectedEdgeId || Boolean(e.selected);
          const baseStyle = getEdgeStyle(e.type);
          return {
            ...e,
            type: "editableSmoothstep",
            selected,
            style: {
              ...baseStyle,
              stroke: selected ? "var(--color-accent)" : baseStyle.stroke,
              strokeWidth: selected
                ? Number(baseStyle.strokeWidth || 2) + 1.25
                : baseStyle.strokeWidth,
              ...(dim ? { opacity: 0.25 } : {}),
            },
            animated: getEdgeAnimated(e.type),
            interactionWidth: selected ? 28 : 20,
            data: {
              ...(e.data || {}),
              kind: e.type,
              onStepPositionChange: handleEdgeStepPositionChange,
            },
          };
        }),
    [
      edges,
      handleEdgeStepPositionChange,
      hiddenIds,
      nodeById,
      selectedEdgeId,
      showHidden,
      showSecurityDetails,
    ],
  );
  useEffect(() => {
    if (!id) return;
    getCanvas(id)
      .then(loadCanvasState)
      .catch((e: Error) => setError(e.message));
  }, [id, loadCanvasState]);

  useEffect(() => {
    refreshDeploymentHistory();
  }, [refreshDeploymentHistory]);

  useEffect(() => {
    if (
      planDeployment?.status === "success" ||
      planDeployment?.status === "approved" ||
      planDeployment?.status === "applied" ||
      planDeployment?.status === "destroyed" ||
      planDeployment?.status === "failed"
    ) {
      refreshDeploymentHistory();
    }
  }, [planDeployment?.status, refreshDeploymentHistory]);

  useEffect(() => {
    listCanvasFragments()
      .then(setFragments)
      .catch(() => {
        setFragments([]);
      });
  }, []);

  useEffect(() => {
    if (!loaded) return;
    const snapshot = cloneGraphSnapshot({ nodes, edges });
    latestSnapshotRef.current = snapshot;
    const fingerprint = graphFingerprint(snapshot.nodes, snapshot.edges);
    setSaveStatus((current) => {
      if (current === "saving") return current;
      return fingerprint === savedFingerprintRef.current ? "saved" : "dirty";
    });

    if (restoringHistoryRef.current) {
      restoringHistoryRef.current = false;
      return;
    }
    if (nodeDragInProgressRef.current) {
      return;
    }

    const history = historyRef.current;
    const cursor = historyCursorRef.current;
    const currentSnapshot = history[cursor];
    if (
      currentSnapshot &&
      graphFingerprint(currentSnapshot.nodes, currentSnapshot.edges) === fingerprint
    ) {
      return;
    }

    const nextHistory = [
      ...history.slice(0, cursor + 1),
      cloneGraphSnapshot(snapshot),
    ].slice(-80);
    historyRef.current = nextHistory;
    historyCursorRef.current = nextHistory.length - 1;
  }, [edges, loaded, nodes]);

  const handleSave = useCallback(async () => {
    if (!loaded || !id) return false;
    const snapshot = cloneGraphSnapshot(latestSnapshotRef.current);
    const fingerprint = graphFingerprint(snapshot.nodes, snapshot.edges);
    if (fingerprint === savedFingerprintRef.current) {
      setSaveStatus("saved");
      return true;
    }

    setSaveStatus("saving");
    try {
      const graph = flowToCanvasGraph(snapshot.nodes, snapshot.edges);
      const updated = await updateCanvas(id, { graph });
      setCanvas(updated);
      savedFingerprintRef.current = fingerprint;
      setSaveStatus("saved");
      return true;
    } catch (e) {
      setSaveStatus("error");
      setError((e as Error).message);
      return false;
    }
  }, [id, loaded]);

  const handleInsertFragment = useCallback(
    async (fragmentId: string) => {
      if (!id || insertingFragment) return;
      setInsertingFragment(true);
      try {
        const bounds = reactFlowWrapper.current?.getBoundingClientRect();
        const position = bounds
          ? screenToFlowPosition({
              x: bounds.left + 120,
              y: bounds.top + 96,
            })
          : { x: 80, y: 80 };
        const updated = await insertCanvasFragment(id, {
          fragment_id: fragmentId,
          x: Math.round(position.x),
          y: Math.round(position.y),
        });
        loadCanvasState(updated);
        showNotice("기본 구성을 추가했습니다.", "success");
      } catch (e) {
        const message = (e as Error).message;
        setError(message);
        showNotice(message, "error");
      } finally {
        setInsertingFragment(false);
      }
    },
    [
      id,
      insertingFragment,
      loadCanvasState,
      screenToFlowPosition,
      showNotice,
    ],
  );

  useEffect(() => {
    if (!loaded || !autoSaveEnabled) return;
    if (saveStatus !== "dirty" && saveStatus !== "error") return;
    const timer = setTimeout(() => {
      void handleSave();
    }, 1500);
    return () => clearTimeout(timer);
  }, [autoSaveEnabled, handleSave, loaded, saveStatus]);

  useEffect(() => {
    if (!loaded) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      const snapshot = latestSnapshotRef.current;
      if (
        graphFingerprint(snapshot.nodes, snapshot.edges) ===
        savedFingerprintRef.current
      ) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [loaded]);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      const shouldReassignParents = changes.some(
        (change) => change.type === "dimensions",
      );
      const selectedChange = changes.find(
        (change) => change.type === "select" && change.selected,
      );
      if (selectedChange && "id" in selectedChange) {
        setSelectedNodeId(selectedChange.id);
        setSelectedEdgeId(null);
        setAwsPanelOpen(false);
        setKubernetesPanelOpen(false);
      }
      setNodes((nds) => {
        const next = applyNodeChanges(changes, nds);
        return shouldReassignParents ? assignParentGroups(next) : next;
      });
    },
    [],
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const selectedChange = changes.find(
        (change) => change.type === "select" && change.selected,
      );
      if (selectedChange && "id" in selectedChange) {
        setSelectedEdgeId(selectedChange.id);
        setSelectedNodeId(null);
        setAwsPanelOpen(false);
        setKubernetesPanelOpen(false);
      }
      setEdges((eds) => applyEdgeChanges(changes, eds));
    },
    [],
  );
  const onConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);
      const inferred = inferEdgeKind(sourceNode?.type, targetNode?.type);
      setEdges((eds) =>
        addEdge(
          {
            ...connection,
            id: `e-${crypto.randomUUID()}`,
            type: inferred,
            data: { properties: {} },
          },
          eds,
        ),
      );
    },
    [nodes],
  );
  const onReconnect = useCallback<OnReconnect<Edge>>(
    (oldEdge, newConnection) => {
      setEdges((eds) =>
        eds.map((edge) =>
          edge.id === oldEdge.id
            ? {
                ...edge,
                source: newConnection.source || edge.source,
                target: newConnection.target || edge.target,
                sourceHandle: newConnection.sourceHandle,
                targetHandle: newConnection.targetHandle,
              }
            : edge,
        ),
      );
    },
    [],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData("application/eolgae-node");
      if (!type) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      const snappedPosition = snapPosition(position);

      const groupDef = getGroupTypeDef(type);
      if (groupDef) {
        const newGroup: Node = {
          id: `group-${crypto.randomUUID()}`,
          type,
          position: snappedPosition,
          width: groupDef.defaultSize.width,
          height: groupDef.defaultSize.height,
          data: {
            display_name: groupDef.displayName,
            properties: { ...groupDef.defaultProperties },
            groupLabelSize: 9,
            showCidr: true,
            showAz: true,
          },
          // ReactFlow wrapper div 자체를 pointer-events:none 으로.
          // → 내부 빈 공간 클릭 = 통과 (자식 노드 / 캔버스 우선).
          // strip/header/NodeResizer handle 만 명시 pointer-events:auto 라 그것들만 활성.
          style: { pointerEvents: "none" },
          zIndex: -1,
          selectable: true,
          draggable: true,
        };
        const aligned = findMagneticAlignment(newGroup, nodes);
        setNodes((nds) =>
          assignParentGroups([
            { ...newGroup, position: aligned.position },
            ...nds,
          ]),
        );
        return;
      }

      const def = getNodeTypeDef(type);
      if (!def) return;

      const newNode: Node = {
        id: `node-${crypto.randomUUID()}`,
        type,
        position: snappedPosition,
        data: {
          display_name: def.displayName,
          properties: { ...def.defaultProperties },
        },
      };
      const aligned = findMagneticAlignment(newNode, nodes);
      if (type === SECURITY_GROUP_TYPE) {
        setShowSecurityDetails(true);
      }
      setNodes((nds) =>
        assignParentGroups([...nds, { ...newNode, position: aligned.position }]),
      );
    },
    [nodes, screenToFlowPosition],
  );

  const onNodeDragStart = useCallback(() => {
    nodeDragInProgressRef.current = true;
    dragSnapshotRef.current = {
      positions: new Map(nodes.map((n) => [n.id, { ...n.position }])),
    };
  }, [nodes]);

  const onNodeDrag = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const aligned = findMagneticAlignment(
        node,
        getAlignmentCandidates(node, nodes),
      );
      const wrapperRect = reactFlowWrapper.current?.getBoundingClientRect();
      if (!wrapperRect) {
        setAlignmentGuides({});
        return;
      }
      setAlignmentGuides({
        ...(aligned.guides.x != null
          ? {
              x:
                flowToScreenPosition({ x: aligned.guides.x, y: 0 }).x -
                wrapperRect.left,
            }
          : {}),
        ...(aligned.guides.y != null
          ? {
              y:
                flowToScreenPosition({ x: 0, y: aligned.guides.y }).y -
                wrapperRect.top,
            }
          : {}),
      });
    },
    [flowToScreenPosition, nodes],
  );

  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const aligned = findMagneticAlignment(
        node,
        getAlignmentCandidates(node, nodes),
      );
      const position = snapPosition(aligned.position);
      const snapshot = dragSnapshotRef.current;
      const startPosition = snapshot?.positions.get(node.id);
      const delta = startPosition
        ? {
            x: position.x - startPosition.x,
            y: position.y - startPosition.y,
          }
        : { x: 0, y: 0 };
      const descendants = getDescendantIds(nodes, node.id);

      nodeDragInProgressRef.current = false;
      setNodes((nds) => {
        const moved = nds.map((n) => {
          if (n.id === node.id) return { ...n, position };
          if (descendants.has(n.id)) {
            return {
              ...n,
              position: {
                x: n.position.x + delta.x,
                y: n.position.y + delta.y,
              },
            };
          }
          return n;
        });
        return assignParentGroups(moved);
      });
      setAlignmentGuides({});
      dragSnapshotRef.current = null;
    },
    [nodes],
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
    setSelectedEdgeId(null);
    setAwsPanelOpen(false);
    setKubernetesPanelOpen(false);
  }, []);

  const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    setSelectedEdgeId(edge.id);
    setSelectedNodeId(null);
    setAwsPanelOpen(false);
    setKubernetesPanelOpen(false);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  }, []);

  const restoreSnapshot = useCallback((snapshot: GraphSnapshot) => {
    restoringHistoryRef.current = true;
    const restored = cloneGraphSnapshot(snapshot);
    setNodes(restored.nodes);
    setEdges(restored.edges);
  }, []);

  const handleUndo = useCallback(() => {
    const cursor = historyCursorRef.current;
    if (cursor <= 0) return;
    const nextCursor = cursor - 1;
    historyCursorRef.current = nextCursor;
    restoreSnapshot(historyRef.current[nextCursor]);
  }, [restoreSnapshot]);

  const handleRedo = useCallback(() => {
    const cursor = historyCursorRef.current;
    if (cursor >= historyRef.current.length - 1) return;
    const nextCursor = cursor + 1;
    historyCursorRef.current = nextCursor;
    restoreSnapshot(historyRef.current[nextCursor]);
  }, [restoreSnapshot]);

  const getSelectedNodeIds = useCallback(() => {
    const ids = new Set(
      nodes.filter((node) => node.selected).map((node) => node.id),
    );
    if (selectedNodeId) ids.add(selectedNodeId);
    return ids;
  }, [nodes, selectedNodeId]);

  const handleDeleteSelection = useCallback(() => {
    const selectedNodeIds = getSelectedNodeIds();
    if (selectedNodeIds.size > 0) {
      for (const nodeId of [...selectedNodeIds]) {
        for (const descendantId of getDescendantIds(nodes, nodeId)) {
          selectedNodeIds.add(descendantId);
        }
      }
      setNodes((nds) => nds.filter((node) => !selectedNodeIds.has(node.id)));
      setEdges((eds) =>
        eds.filter(
          (edge) =>
            !selectedNodeIds.has(edge.source) &&
            !selectedNodeIds.has(edge.target),
        ),
      );
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      return;
    }

    const selectedEdgeIds = new Set(
      edges
        .filter((edge) => edge.selected || edge.id === selectedEdgeId)
        .map((edge) => edge.id),
    );
    if (selectedEdgeIds.size === 0) return;
    setEdges((eds) => eds.filter((edge) => !selectedEdgeIds.has(edge.id)));
    setSelectedEdgeId(null);
  }, [edges, getSelectedNodeIds, nodes, selectedEdgeId]);

  const handleCopySelection = useCallback(() => {
    const selectedNodeIds = getSelectedNodeIds();
    if (selectedNodeIds.size === 0) return;
    for (const nodeId of [...selectedNodeIds]) {
      for (const descendantId of getDescendantIds(nodes, nodeId)) {
        selectedNodeIds.add(descendantId);
      }
    }
    const copiedNodes = nodes.filter((node) => selectedNodeIds.has(node.id));
    const copiedEdges = edges.filter(
      (edge) =>
        selectedNodeIds.has(edge.source) && selectedNodeIds.has(edge.target),
    );
    clipboardRef.current = cloneGraphSnapshot({
      nodes: copiedNodes,
      edges: copiedEdges,
    });
    showNotice(`${copiedNodes.length}개 리소스를 복사했습니다.`, "info");
  }, [edges, getSelectedNodeIds, nodes, showNotice]);

  const handlePasteSelection = useCallback(() => {
    const clipboard = clipboardRef.current;
    if (!clipboard || clipboard.nodes.length === 0) return;

    const idMap = new Map<string, string>();
    for (const node of clipboard.nodes) {
      idMap.set(
        node.id,
        node.id.startsWith("group-")
          ? `group-${crypto.randomUUID()}`
          : `node-${crypto.randomUUID()}`,
      );
    }

    const pastedNodeIds = new Set<string>();
    const pastedNodes = clipboard.nodes.map((node) => {
      const nextId = idMap.get(node.id) || `node-${crypto.randomUUID()}`;
      pastedNodeIds.add(nextId);
      const parentGroupId = node.data?.parent_group_id as string | undefined;
      const copiedName = nodeDisplayName(node);
      return {
        ...node,
        id: nextId,
        selected: true,
        position: {
          x: node.position.x + 48,
          y: node.position.y + 48,
        },
        data: {
          ...(clonePlainObject(node.data) || {}),
          display_name: copiedName ? `${copiedName} 복사본` : copiedName,
          parent_group_id:
            parentGroupId && idMap.has(parentGroupId)
              ? idMap.get(parentGroupId)
              : parentGroupId,
        },
      };
    });

    const pastedEdges = clipboard.edges.map((edge) => ({
      ...edge,
      id: `e-${crypto.randomUUID()}`,
      source: idMap.get(edge.source) || edge.source,
      target: idMap.get(edge.target) || edge.target,
      selected: false,
      data: clonePlainObject(edge.data),
    }));

    setNodes((nds) =>
      assignParentGroups([
        ...nds.map((node) => ({ ...node, selected: false })),
        ...pastedNodes,
      ]),
    );
    setEdges((eds) => [
      ...eds.map((edge) => ({ ...edge, selected: false })),
      ...pastedEdges,
    ]);
    setSelectedNodeId(pastedNodes[0]?.id || null);
    setSelectedEdgeId(null);
    showNotice(`${pastedNodes.length}개 리소스를 붙여넣었습니다.`, "success");
  }, [showNotice]);

  useEffect(() => {
    if (!loaded) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      const targetIsEditable = isEditableKeyTarget(event.target);
      const mod = event.metaKey || event.ctrlKey;
      const key = event.key.toLowerCase();

      if (mod && key === "s") {
        event.preventDefault();
        void handleSave();
        return;
      }

      if (targetIsEditable) return;

      if (mod && key === "z") {
        event.preventDefault();
        if (event.shiftKey) {
          handleRedo();
        } else {
          handleUndo();
        }
        return;
      }

      if (mod && key === "y") {
        event.preventDefault();
        handleRedo();
        return;
      }

      if (mod && key === "c") {
        if (hasBrowserTextSelection()) return;
        if (getSelectedNodeIds().size === 0) return;
        event.preventDefault();
        handleCopySelection();
        return;
      }

      if (mod && key === "v") {
        if (!clipboardRef.current) return;
        event.preventDefault();
        handlePasteSelection();
        return;
      }

      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        handleDeleteSelection();
        return;
      }

      if (event.key === "Escape") {
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    handleCopySelection,
    handleDeleteSelection,
    handlePasteSelection,
    handleRedo,
    handleSave,
    handleUndo,
    getSelectedNodeIds,
    loaded,
  ]);

  const handleEdgeUpdate = useCallback(
    (
      edgeId: string,
      updates: { type?: string; properties?: Record<string, unknown> },
    ) => {
      setEdges((eds) =>
        eds.map((e) => {
          if (e.id !== edgeId) return e;
          const next: Edge = { ...e };
          if (updates.type !== undefined) next.type = updates.type;
          if (updates.properties !== undefined) {
            next.data = { ...(e.data || {}), properties: updates.properties };
          }
          return next;
        }),
      );
    },
    [],
  );

  const handleNodeUpdate = useCallback(
    (
      nodeId: string,
      updates: {
        display_name?: string;
        properties?: Record<string, unknown>;
        view?: Record<string, unknown>;
      },
    ) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id !== nodeId) return n;
          const newData = { ...(n.data || {}) };
          if (updates.display_name !== undefined) {
            newData.display_name = updates.display_name;
          }
          if (updates.properties !== undefined) {
            newData.properties = updates.properties;
          }
          if (updates.view !== undefined) {
            Object.assign(newData, updates.view);
          }
          return { ...n, data: newData };
        }),
      );
    },
    [],
  );

  const handleSecurityGroupToggle = useCallback(
    (resourceId: string, securityGroupId: string, attached: boolean) => {
      setEdges((eds) => {
        const hasExisting = eds.some((edge) => {
          const sourceTargetMatch =
            (edge.source === resourceId && edge.target === securityGroupId) ||
            (edge.source === securityGroupId && edge.target === resourceId);
          return (
            sourceTargetMatch &&
            isAssociationEdgeForSlot(edge, SECURITY_GROUP_TYPE)
          );
        });

        if (attached) {
          if (hasExisting) return eds;
          return [
            ...eds,
            {
              id: `e-${crypto.randomUUID()}`,
              source: resourceId,
              target: securityGroupId,
              type: "reference",
              data: { properties: {} },
            },
          ];
        }

        return eds.filter((edge) => {
          const sourceTargetMatch =
            (edge.source === resourceId && edge.target === securityGroupId) ||
            (edge.source === securityGroupId && edge.target === resourceId);
          return !(
            sourceTargetMatch &&
            isAssociationEdgeForSlot(edge, SECURITY_GROUP_TYPE)
          );
        });
      });
    },
    [],
  );

  const handleSecurityGroupCreate = useCallback(
    (resourceId: string) => {
      const resource = nodes.find((node) => node.id === resourceId);
      const def = getNodeTypeDef(SECURITY_GROUP_TYPE);
      if (!resource || !def) return;

      const sgId = `node-${crypto.randomUUID()}`;
      const parentVpcId = nearestAncestorIdOfType(
        resource,
        nodeById,
        "aws.ec2.vpc",
      );
      const displayName = `${nodeDisplayName(resource)} SG`;
      const sgNode: Node = {
        id: sgId,
        type: SECURITY_GROUP_TYPE,
        position: {
          x: resource.position.x + 240,
          y: resource.position.y,
        },
        data: {
          display_name: displayName,
          properties: { ...def.defaultProperties },
          parent_group_id: parentVpcId,
        },
      };

      setNodes((nds) => [...nds, sgNode]);
      setEdges((eds) => [
        ...eds,
        {
          id: `e-${crypto.randomUUID()}`,
          source: resourceId,
          target: sgId,
          type: "reference",
          data: { properties: {} },
        },
      ]);
    },
    [nodeById, nodes],
  );

  const handleSecurityGroupSelect = useCallback((securityGroupId: string) => {
    setShowSecurityDetails(true);
    setSelectedNodeId(securityGroupId);
    setSelectedEdgeId(null);
  }, []);

  const handleToggleHidden = useCallback(
    (nodeId: string, hidden: boolean) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...(n.data || {}), hidden } }
            : n,
        ),
      );
      // 숨기는데 '보기' 모드가 아니면 패널 닫기 (노드가 사라지므로)
      if (hidden && !showHidden) setSelectedNodeId(null);
    },
    [showHidden],
  );

  const handleGenerateTofu = useCallback(async () => {
    if (!id) return;
    setGenerating(true);
    try {
      if (!(await handleSave())) return;
      const result = await generateTofu(id);
      setTfPreview(result);
      setKubernetesPreview(null);
      setKubernetesValidation(null);
      setTofuPlan(null);
      setPlanDeployment(null);
      setSelectedNodeId(null);
      setFeedbackOpen(false);
      setIacPanelOpen(true);
      setRunPanelOpen(true);
      setSidePanelsCollapsed(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }, [handleSave, id]);

  const handleGenerateKubernetesYaml = useCallback(async () => {
    if (!id) return;
    setGenerating(true);
    try {
      if (!(await handleSave())) return;
      const [result, validation] = await Promise.all([
        generateKubernetesYaml(id),
        validateKubernetesCanvas(id),
      ]);
      setKubernetesPreview(result);
      setKubernetesValidation(validation);
      setTfPreview(null);
      setTofuPlan(null);
      setPlanDeployment(null);
      setSelectedNodeId(null);
      setFeedbackOpen(false);
      setIacPanelOpen(true);
      setRunPanelOpen(true);
      setSidePanelsCollapsed(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  }, [handleSave, id, setFeedbackOpen, setPlanDeployment, setTofuPlan]);

  const handleRunPlanWithSave = useCallback(async () => {
    if (!(await handleSave())) return;
    await handleRunPlan();
  }, [handleRunPlan, handleSave]);

  const handleRunDestroyPlanWithSave = useCallback(async () => {
    if (!(await handleSave())) return;
    await handleRunDestroyPlan();
  }, [handleRunDestroyPlan, handleSave]);

  const handleRequestFeedbackWithSave = useCallback(async () => {
    if (!(await handleSave())) return;
    await handleRequestFeedback();
  }, [handleRequestFeedback, handleSave]);

  const handleAwsAccountUpdated = useCallback((awsAccount: AwsAccount) => {
    setCanvas((current) =>
      current ? { ...current, aws_account: awsAccount } : current,
    );
  }, []);

  const startEditingName = useCallback(() => {
    setNameInput(canvas?.name || "");
    setEditingName(true);
  }, [canvas?.name]);

  const handleNameSave = useCallback(async () => {
    if (!id || !canvas) {
      setEditingName(false);
      return;
    }
    const trimmed = nameInput.trim();
    if (!trimmed || trimmed === canvas.name) {
      setEditingName(false);
      return;
    }
    try {
      const updated = await updateCanvas(id, { name: trimmed });
      setCanvas(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setEditingName(false);
    }
  }, [id, canvas, nameInput]);

  const handleTfDownload = useCallback(() => {
    if (!tfPreview) return;
    const blob = new Blob([tfPreview.tf], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = tfPreview.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [tfPreview]);

  const handleKubernetesYamlDownload = useCallback(() => {
    if (!kubernetesPreview) return;
    const blob = new Blob([kubernetesPreview.yaml], {
      type: "text/yaml;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = kubernetesPreview.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [kubernetesPreview]);

  if (error || !canvas) return <CanvasStatusView error={error} />;

  const actionDisabled = nodes.length === 0;

  return (
    <div className="flex h-screen w-screen bg-[var(--color-bg)]">
      <PaletteSidebar
        collapsed={!paletteOpen}
        canvasKind={canvas.canvas_kind || "aws"}
        fragments={fragments}
        insertingFragment={insertingFragment}
        onToggle={() => setPaletteOpen((v) => !v)}
        onInsertFragment={handleInsertFragment}
      />
      <div
        ref={reactFlowWrapper}
        className="relative flex-1"
        onDrop={onDrop}
        onDragOver={onDragOver}
      >
        <CanvasToolbar
          canvasName={canvas.name}
          canvasState={canvas.state}
          saveStatus={saveStatus}
          autoSaveEnabled={autoSaveEnabled}
          editingName={editingName}
          nameInput={nameInput}
          onSave={handleSave}
          onAutoSaveChange={setAutoSaveEnabled}
          onNameInputChange={setNameInput}
          onNameEditStart={startEditingName}
          onNameSave={handleNameSave}
          onNameEditCancel={() => setEditingName(false)}
        />

        {(canvas.canvas_kind || "aws") === "kubernetes" ? (
          <KubernetesResourceMapStage
            nodes={displayNodes}
            edges={displayEdges}
            selectedNodeId={selectedNodeId}
            rightPanelInsetPx={resourceMapRightInsetPx}
            onSelectNode={handleKubernetesNodeSelect}
          />
        ) : (
          <CanvasFlowStage
            nodes={displayNodes}
            edges={displayEdges}
            alignmentGuides={alignmentGuides}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onReconnect={onReconnect}
            onNodeDragStart={onNodeDragStart}
            onNodeDrag={onNodeDrag}
            onNodeDragStop={onNodeDragStop}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
          />
        )}

        {feedbackOpen && (
          <FeedbackPanel
            feedback={feedback}
            loading={feedbackLoading}
            streamingText={streamingText}
            error={feedbackError}
            isStale={isStale}
            autoReflect={autoReflect}
            canStart={!actionDisabled}
            heightVh={feedbackPanelHeightVh}
            onClose={() => setFeedbackOpen(false)}
            onStart={handleRequestFeedbackWithSave}
            onStop={handleStopFeedback}
            onAutoReflectChange={setAutoReflect}
            onHeightVhChange={setFeedbackPanelHeightVh}
            onItemClick={handleFeedbackItemClick}
          />
        )}

        {notice && (
          <CanvasToast
            key={notice.id}
            message={notice.message}
            tone={notice.tone}
            onClose={() => setNotice(null)}
          />
        )}

        <CanvasSidePanels
          canvasId={id}
          canvasKind={canvas.canvas_kind || "aws"}
          canvasState={canvas.state}
          awsAccount={canvas.aws_account}
          selectedNode={selectedNode}
          selectedEdge={selectedEdge}
          nodes={nodes}
          edges={edges}
          tfPreview={tfPreview}
          kubernetesPreview={kubernetesPreview}
          kubernetesValidation={kubernetesValidation}
          tofuPlan={tofuPlan}
          planDeployment={planDeployment}
          deploymentHistory={deploymentHistory}
          iacPanelOpen={iacPanelOpen}
          awsPanelOpen={awsPanelOpen}
          kubernetesPanelOpen={kubernetesPanelOpen}
          inspectorOpen={inspectorOpen}
          runPanelOpen={runPanelOpen}
          sidePanelsCollapsed={sidePanelsCollapsed}
          feedbackPanelOpen={feedbackOpen}
          inspectorBottomInset={inspectorBottomInset}
          inspectorWidth={inspectorWidth}
          runPanelHeightVh={runPanelHeightVh}
          awsVerified={canvas.aws_account?.binding_status === "verified"}
          feedbackLoading={feedbackLoading}
          hasFeedback={Boolean(feedback)}
          isStale={isStale}
          autoReflect={autoReflect}
          generating={generating}
          planning={planning}
          applying={applying}
          destroying={destroying}
          actionDisabled={actionDisabled}
          hiddenCount={hiddenIds.size}
          showHidden={showHidden}
          containedNodeCount={containedNodeCount}
          showContainmentBadges={showContainmentBadges}
          securityGroupOptions={securityGroupOptions}
          onInspectorToggle={() => setInspectorOpen((v) => !v)}
          onRunPanelToggle={() => setRunPanelOpen((v) => !v)}
          onSidePanelsToggle={() => setSidePanelsCollapsed((v) => !v)}
          onInspectorWidthChange={setInspectorWidth}
          onRunPanelHeightChange={setRunPanelHeightVh}
          onAwsToggle={() => {
            setInspectorOpen(true);
            setSidePanelsCollapsed(false);
            setKubernetesPanelOpen(false);
            setAwsPanelOpen((v) => !v);
          }}
          onKubernetesToggle={handleKubernetesOpenFromInspector}
          onFeedbackOpen={handleFeedbackOpenFromToolbar}
          onIacOpen={handleIacOpenFromToolbar}
          onGenerateTofu={handleGenerateTofu}
          onGenerateKubernetesYaml={handleGenerateKubernetesYaml}
          onRunPlan={handleRunPlanWithSave}
          onApplyPlan={handleApproveAndApply}
          onDestroyPlan={handleRunDestroyPlanWithSave}
          onDestroyApply={handleApproveAndDestroy}
          onToggleShowHidden={() => setShowHidden((v) => !v)}
          onToggleContainmentBadges={() =>
            setShowContainmentBadges((v) => !v)
          }
          onNodeChange={handleNodeUpdate}
          onNodeClose={() => setSelectedNodeId(null)}
          onToggleHidden={handleToggleHidden}
          onSecurityGroupToggle={handleSecurityGroupToggle}
          onSecurityGroupCreate={handleSecurityGroupCreate}
          onSecurityGroupSelect={handleSecurityGroupSelect}
          onEdgeChange={handleEdgeUpdate}
          onEdgeClose={() => setSelectedEdgeId(null)}
          onTfClose={() => {
            setIacPanelOpen(false);
            setRunPanelOpen(false);
          }}
          onTfDownload={handleTfDownload}
          onKubernetesYamlClose={() => {
            setIacPanelOpen(false);
            setRunPanelOpen(false);
            setKubernetesValidation(null);
          }}
          onKubernetesYamlDownload={handleKubernetesYamlDownload}
          onPlanClose={() => {
            setIacPanelOpen(false);
            setRunPanelOpen(false);
          }}
          onAwsClose={() => setAwsPanelOpen(false)}
          onKubernetesClose={() => setKubernetesPanelOpen(false)}
          onAwsUpdated={handleAwsAccountUpdated}
          onKubernetesNodeSelect={handleKubernetesNodeSelect}
        />
      </div>
    </div>
  );
}

function CanvasToast({
  message,
  tone,
  onClose,
}: {
  message: string;
  tone: CanvasNotice["tone"];
  onClose: () => void;
}) {
  const toneClass =
    tone === "success"
      ? "border-[var(--color-success)] text-[var(--color-success)]"
      : tone === "error"
        ? "border-[var(--color-danger)] text-[var(--color-danger)]"
        : "border-[var(--color-accent)] text-[var(--color-accent)]";

  return (
    <div
      className={`absolute right-4 top-16 z-[30] flex max-w-sm items-start gap-3 rounded-md border bg-[var(--color-surface)] px-3 py-2 text-sm shadow-[var(--shadow-lg)] ${toneClass}`}
      role="status"
    >
      <span className="min-w-0 flex-1 text-[var(--color-text)]">{message}</span>
      <button
        type="button"
        onClick={onClose}
        className="shrink-0 rounded px-1 text-[var(--color-text-subtle)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)]"
        aria-label="알림 닫기"
      >
        x
      </button>
    </div>
  );
}

export default function CanvasPage() {
  return (
    <ReactFlowProvider>
      <NodeDensityProvider>
        <CanvasInner />
      </NodeDensityProvider>
    </ReactFlowProvider>
  );
}
