import { type Edge, type Node } from "@xyflow/react";

import { getGroupTypeDef } from "@/lib/group-types";
import {
  DEFAULT_EDGE_KIND,
} from "@/lib/edge-types";
import { type CanvasGraph } from "@/lib/api";


export function canvasGraphToFlow(graph: CanvasGraph): {
  nodes: Node[];
  edges: Edge[];
} {
  const nodes: Node[] = (graph.nodes || []).map((n) => {
    const groupDef = getGroupTypeDef(n.type);
    const meta = (n.metadata || {}) as Record<string, unknown>;
    const node: Node = {
      id: n.id,
      type: n.type,
      position: n.position,
      data: {
        display_name: n.display_name || "",
        properties: n.properties || {},
        hidden: Boolean(meta.hidden),
        parent_group_id: n.parent_group_id ?? null,
        groupLabelSize:
          typeof meta.groupLabelSize === "string" ||
          typeof meta.groupLabelSize === "number"
            ? meta.groupLabelSize
            : 9,
        showCidr: meta.showCidr !== false,
        showAz: meta.showAz !== false,
      },
    };
    if (n.size) {
      node.width = n.size.width;
      node.height = n.size.height;
    }
    if (groupDef) {
      node.style = { pointerEvents: "none" };
      node.zIndex = -1;
      node.selectable = true;
      node.draggable = true;
      if (!n.size) {
        node.width = groupDef.defaultSize.width;
        node.height = groupDef.defaultSize.height;
      }
    }
    return node;
  });

  const edges: Edge[] = (graph.edges || []).map((e) => {
    const meta = (e.metadata || {}) as Record<string, unknown>;
    const edge: Edge = {
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.type || DEFAULT_EDGE_KIND,
      data: {
        properties: e.properties || {},
        ...(typeof meta.pathStepPosition === "number"
          ? { pathStepPosition: meta.pathStepPosition }
          : {}),
      },
    };
    if (typeof meta.sourceHandle === "string") {
      edge.sourceHandle = meta.sourceHandle;
    }
    if (typeof meta.targetHandle === "string") {
      edge.targetHandle = meta.targetHandle;
    }
    return edge;
  });

  return { nodes, edges };
}


export function flowToCanvasGraph(nodes: Node[], edges: Edge[]): CanvasGraph {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type || "default",
      display_name: (n.data?.display_name as string) || "",
      position: n.position,
      size:
        n.width != null && n.height != null
          ? { width: n.width, height: n.height }
          : undefined,
      properties: (n.data?.properties as Record<string, unknown>) || {},
      parent_group_id:
        (n.data?.parent_group_id as string | null | undefined) ?? null,
      metadata: {
        hidden: Boolean(n.data?.hidden),
        groupLabelSize:
          (n.data?.groupLabelSize as string | number | undefined) || 9,
        showCidr: n.data?.showCidr !== false,
        showAz: n.data?.showAz !== false,
      },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.type || DEFAULT_EDGE_KIND,
      properties:
        ((e.data as { properties?: Record<string, unknown> } | undefined)
          ?.properties) || {},
      metadata: {
        ...(e.sourceHandle ? { sourceHandle: e.sourceHandle } : {}),
        ...(e.targetHandle ? { targetHandle: e.targetHandle } : {}),
        ...(typeof (e.data as { pathStepPosition?: unknown } | undefined)
          ?.pathStepPosition === "number"
          ? {
              pathStepPosition: (e.data as { pathStepPosition: number })
                .pathStepPosition,
            }
          : {}),
      },
    })),
    groups: [],
  };
}
