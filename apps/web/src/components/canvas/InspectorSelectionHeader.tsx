import { type Edge, type Node } from "@xyflow/react";

export function InspectorSelectionHeader({
  awsPanelOpen,
  kubernetesPanelOpen,
  selectedNode,
  selectedEdge,
}: {
  awsPanelOpen: boolean;
  kubernetesPanelOpen: boolean;
  selectedNode?: Node;
  selectedEdge?: Edge;
}) {
  const title = awsPanelOpen
    ? "AWS 계정"
    : kubernetesPanelOpen
      ? "Kubernetes"
      : selectedNode
        ? String(
            selectedNode.data?.display_name ||
              selectedNode.data?.label ||
              selectedNode.id,
          )
        : selectedEdge
          ? "연결"
          : "선택 없음";
  const meta = awsPanelOpen
    ? "Account binding"
    : kubernetesPanelOpen
      ? "Resource tree preview"
      : selectedNode
        ? selectedNode.type || "resource"
        : selectedEdge
          ? `${selectedEdge.source} -> ${selectedEdge.target}`
          : "캔버스에서 리소스나 연결선을 선택하세요.";

  return (
    <div className="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">
      <div className="truncate text-sm font-semibold text-[var(--color-text)]">
        {title}
      </div>
      <div className="mt-0.5 truncate text-[11px] text-[var(--color-text-muted)]">
        {meta}
      </div>
    </div>
  );
}
