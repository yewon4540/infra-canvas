import {
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  SelectionMode,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type OnReconnect,
} from "@xyflow/react";
import { type MouseEvent } from "react";

import { EditableSmoothStepEdge } from "@/components/canvas/EditableSmoothStepEdge";
import { groupNodeTypes } from "@/components/AwsGroup";
import { nodeTypes } from "@/components/AwsNode";
import { SNAP_GRID, type AlignmentGuides } from "@/lib/canvas-graph";

const edgeTypes = {
  editableSmoothstep: EditableSmoothStepEdge,
};

type CanvasFlowStageProps = {
  nodes: Node[];
  edges: Edge[];
  alignmentGuides: AlignmentGuides;
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  onReconnect: OnReconnect<Edge>;
  onNodeDragStart: () => void;
  onNodeDrag: (event: MouseEvent, node: Node) => void;
  onNodeDragStop: (event: MouseEvent, node: Node) => void;
  onNodeClick: (event: MouseEvent, node: Node) => void;
  onEdgeClick: (event: MouseEvent, edge: Edge) => void;
  onPaneClick: () => void;
};

export function CanvasFlowStage({
  nodes,
  edges,
  alignmentGuides,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onReconnect,
  onNodeDragStart,
  onNodeDrag,
  onNodeDragStop,
  onNodeClick,
  onEdgeClick,
  onPaneClick,
}: CanvasFlowStageProps) {
  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={{ ...nodeTypes, ...groupNodeTypes }}
        edgeTypes={edgeTypes}
        connectionMode={ConnectionMode.Loose}
        snapToGrid
        snapGrid={SNAP_GRID}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onReconnect={onReconnect}
        edgesReconnectable
        reconnectRadius={16}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        selectionKeyCode="Shift"
        multiSelectionKeyCode="Shift"
        selectionMode={SelectionMode.Full}
        fitView
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>

      {alignmentGuides.x != null && (
        <div
          className="pointer-events-none absolute bottom-0 top-0 z-[5] w-px bg-[var(--color-accent)]/70"
          style={{ left: alignmentGuides.x }}
        />
      )}
      {alignmentGuides.y != null && (
        <div
          className="pointer-events-none absolute left-0 right-0 z-[5] h-px bg-[var(--color-accent)]/70"
          style={{ top: alignmentGuides.y }}
        />
      )}
    </>
  );
}
