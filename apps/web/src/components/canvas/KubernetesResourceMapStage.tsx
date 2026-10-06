"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type OnNodeDrag,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  buildDiagramRelations,
  buildResourceCards,
} from "@/lib/canvas/kubernetesResourceMap";
import {
  buildKubernetesTopology,
  clampPosition,
  type GroupTone,
  type TopologyNodeData,
} from "@/lib/canvas/kubernetesTopology";

const KUBE_ICON_BASE = "/icons/kube/icons/svg/resources/labeled";
const KUBE_KIND_ICONS: Record<string, string> = {
  Namespace: "ns.svg",
  Deployment: "deploy.svg",
  ReplicaSet: "rs.svg",
  Pod: "pod.svg",
  Service: "svc.svg",
  Ingress: "ing.svg",
  HPA: "hpa.svg",
  ConfigMap: "cm.svg",
  SecretRef: "secret.svg",
  PVC: "pvc.svg",
  EndpointSlice: "ep.svg",
  NetworkPolicy: "netpol.svg",
  ResourceQuota: "quota.svg",
  LimitRange: "limits.svg",
};

const nodeTypes = {
  kubeTopology: KubeTopologyNode,
  kubeGroup: KubeGroupNode,
};

export function KubernetesResourceMapStage({
  nodes,
  edges,
  selectedNodeId,
  rightPanelInsetPx = 0,
  onSelectNode,
}: {
  nodes: Node[];
  edges: Edge[];
  selectedNodeId: string | null;
  rightPanelInsetPx?: number;
  onSelectNode: (nodeId: string) => void;
}) {
  const resources = useMemo(() => buildResourceCards(nodes, edges), [nodes, edges]);
  const layoutKey = useMemo(
    () =>
      resources
        .map((resource) =>
          [
            resource.id,
            resource.kind,
            resource.namespace,
            resource.name,
          ].join(":"),
        )
        .join("|"),
    [resources],
  );
  const relationCount = useMemo(
    () => buildDiagramRelations(resources, edges).length,
    [resources, edges],
  );
  const namespaces = new Set(resources.map((resource) => resource.namespace)).size;
  const topology = useMemo(
    () => buildKubernetesTopology(resources, selectedNodeId, onSelectNode),
    [resources, selectedNodeId, onSelectNode],
  );
  const [customPositions, setCustomPositions] = useState<
    Record<string, { x: number; y: number }>
  >({});
  const flowInstanceRef = useRef<ReactFlowInstance<
    Node<TopologyNodeData>,
    Edge
  > | null>(null);
  const fitResourceNodes = useCallback((duration = 180) => {
    window.requestAnimationFrame(() => {
      const instance = flowInstanceRef.current;
      if (!instance) return;
      instance.fitView({
        padding: 0.24,
        duration,
        maxZoom: 1,
        nodes: instance
          .getNodes()
          .filter((node) => !node.data.group)
          .map((node) => ({ id: node.id })),
      });
    });
  }, []);
  const visibleNodes = useMemo<Node<TopologyNodeData>[]>(
    () =>
      topology.nodes.map((node) =>
        customPositions[node.id] && !node.data.group
          ? {
              ...node,
              draggable: true,
              position: customPositions[node.id],
            }
          : { ...node, draggable: !node.data.group },
      ),
    [customPositions, topology.nodes],
  );
  const handleNodeDragStop: OnNodeDrag<Node<TopologyNodeData>> = useCallback(
    (_event, node) => {
      setCustomPositions((current) => {
        if (node.data.group) return current;
        return {
          ...current,
          [node.id]: clampPosition(node.position, node.data.bounds),
        };
      });
    },
    [],
  );
  const resetLayout = useCallback(() => {
    setCustomPositions({});
    fitResourceNodes(240);
  }, [fitResourceNodes]);

  useEffect(() => {
    if (resources.length > 0) fitResourceNodes(0);
  }, [fitResourceNodes, layoutKey, resources.length]);

  return (
    <div
      className="absolute inset-0 bg-[var(--color-bg)] px-6 pb-8 pt-20"
      style={{ paddingRight: `calc(1.5rem + ${rightPanelInsetPx}px)` }}
    >
      <div className="mx-auto flex h-full max-w-7xl flex-col gap-4">
        <div className="flex shrink-0 flex-wrap items-end justify-between gap-3 border-b border-[var(--color-border)] pb-4">
          <div>
            <h2 className="text-xl font-semibold text-[var(--color-text)]">
              Kubernetes Operations Topology
            </h2>
            <p className="mt-1 max-w-3xl text-sm text-[var(--color-text-muted)]">
              Cluster, GitOps, Helm values에서 읽은 구조를 패키지와 리소스 관계,
              runtime 상태, drift/AIOps 판단으로 연결하는 운영 graph입니다.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-right">
            <Metric label="Resources" value={resources.length} />
            <Metric label="Namespaces" value={namespaces} />
            <Metric label="Relations" value={relationCount} />
          </div>
          {resources.length > 0 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={resetLayout}
                className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-2 text-xs font-semibold text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                자동 정렬
              </button>
            </div>
          )}
        </div>

        {resources.length === 0 ? (
          <div className="rounded-md border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface)] p-8 text-sm leading-relaxed text-[var(--color-text-muted)]">
            Kubernetes target 또는 GitOps source를 연결하면 package, workload,
            runtime 관계가 topology로 표시됩니다. Draft 변경이 필요할 때는 리소스를
            추가해 Preview/Diff 후 승인 경로로 반영합니다.
          </div>
        ) : (
          <section className="min-h-0 flex-1 overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
            <ReactFlow
              nodes={visibleNodes}
              edges={topology.edges}
              nodeTypes={nodeTypes}
              onInit={(instance) => {
                flowInstanceRef.current = instance;
                fitResourceNodes(0);
              }}
              onNodeDragStop={handleNodeDragStop}
              nodesDraggable
              nodesConnectable={false}
              elementsSelectable
              minZoom={0.55}
              maxZoom={1.35}
              proOptions={{ hideAttribution: true }}
            >
              <Background gap={24} size={1} />
              <Controls showInteractive={false} />
              <MiniMap pannable zoomable />
            </ReactFlow>
          </section>
        )}
      </div>
    </div>
  );
}

function KubeGroupNode({ data }: NodeProps<Node<TopologyNodeData>>) {
  return (
    <div
      className={`pointer-events-none h-full w-full rounded-lg border border-dashed ${groupToneClass(data.tone)}`}
    >
      <div className="border-b border-current/20 bg-white/45 px-3 py-2 text-xs font-semibold uppercase tracking-wider dark:bg-black/10">
        {data.name}
      </div>
    </div>
  );
}

function KubeTopologyNode({ id, data }: NodeProps<Node<TopologyNodeData>>) {
  return (
    <button
      type="button"
      onClick={() => data.onSelect?.(id)}
      className={
        data.selected
          ? "w-40 rounded-md border border-[var(--color-accent)] bg-[var(--color-accent-soft)] px-2.5 py-2 text-left shadow-[var(--shadow-md)]"
          : data.virtual
            ? "w-40 rounded-md border border-dashed border-slate-400 bg-slate-50 px-2.5 py-2 text-left shadow-[var(--shadow-sm)] dark:border-[var(--color-border-strong)] dark:bg-[var(--color-bg-subtle)]"
            : "w-40 rounded-md border border-slate-300 bg-white px-2.5 py-2 text-left shadow-[var(--shadow-sm)] hover:border-slate-500 dark:border-[var(--color-border)] dark:bg-[var(--color-surface)] dark:hover:border-[var(--color-border-strong)]"
      }
    >
      <div className="flex items-center gap-2">
        <KubeIcon kind={data.iconKind} size={30} />
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-[var(--color-text)]">
            {data.kind}
          </div>
          <div className="mt-0.5 max-w-[6.75rem] truncate text-xs text-[var(--color-text-muted)]">
            {data.name}
          </div>
        </div>
      </div>
      {(data.namespace || data.status) && (
        <div className="mt-1 truncate text-[10px] text-[var(--color-text-subtle)]">
          {data.namespace ? `ns/${data.namespace}` : data.status}
          {data.namespace && data.status ? ` · ${data.status}` : ""}
        </div>
      )}
    </button>
  );
}

function groupToneClass(tone: GroupTone | undefined) {
  if (tone === "traffic") {
    return "border-emerald-300 bg-emerald-50/80 text-emerald-800 dark:border-emerald-700/70 dark:bg-emerald-950/20 dark:text-emerald-200";
  }
  if (tone === "controller") {
    return "border-indigo-300 bg-indigo-50/80 text-indigo-800 dark:border-indigo-700/70 dark:bg-indigo-950/20 dark:text-indigo-200";
  }
  if (tone === "dependencies") {
    return "border-amber-300 bg-amber-50/80 text-amber-800 dark:border-amber-700/70 dark:bg-amber-950/20 dark:text-amber-200";
  }
  return "border-sky-300 bg-sky-50/80 text-sky-800 dark:border-sky-700/70 dark:bg-sky-950/20 dark:text-sky-200";
}

function KubeIcon({ kind, size }: { kind: string; size: number }) {
  const filename = KUBE_KIND_ICONS[kind];
  if (!filename) {
    return (
      <span
        className="inline-block shrink-0 rounded-full bg-[var(--color-accent-soft)]"
        style={{ height: size, width: size }}
      />
    );
  }
  return (
    <img
      src={`${KUBE_ICON_BASE}/${filename}`}
      alt={kind}
      className="shrink-0"
      style={{ height: size, width: size }}
    />
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-[5rem] rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-subtle)]">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold text-[var(--color-text)]">
        {value}
      </div>
    </div>
  );
}
