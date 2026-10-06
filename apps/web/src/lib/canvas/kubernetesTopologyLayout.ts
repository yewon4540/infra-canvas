import { type ResourceCard } from "@/lib/canvas/kubernetesResourceMap";

export type NodeBounds = {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
};

export const WORKLOAD_ROW_GAP = 320;
export const GROUP_HEADER_HEIGHT = 48;
export const NAMESPACE_GAP_X = 1120;
export const NAMESPACE_WIDTH = 1088;
export const TOPOLOGY_NODE_WIDTH = 160;
export const TOPOLOGY_NODE_HEIGHT = 78;
export const TOPOLOGY_COLUMNS = {
  endpoint: 416,
  replicaSet: 640,
  pod: 840,
};

export function boundsWithin(
  x: number,
  y: number,
  width: number,
  height: number,
): NodeBounds {
  return {
    minX: x + 24,
    minY: y + GROUP_HEADER_HEIGHT + 16,
    maxX: x + width - TOPOLOGY_NODE_WIDTH - 24,
    maxY: y + height - TOPOLOGY_NODE_HEIGHT - 24,
  };
}

export function boundsForResource(
  resource: ResourceCard,
  bounds: {
    traffic: NodeBounds;
    controller: NodeBounds;
    dependencies: NodeBounds;
  },
) {
  if (["Ingress", "Service", "EndpointSlice"].includes(resource.kind)) {
    return bounds.traffic;
  }
  if (["ConfigMap", "SecretRef", "PVC"].includes(resource.kind)) {
    return bounds.dependencies;
  }
  return bounds.controller;
}

export function clampPosition(
  position: { x: number; y: number },
  bounds: NodeBounds | undefined,
) {
  if (!bounds) return position;
  return {
    x: Math.min(Math.max(position.x, bounds.minX), bounds.maxX),
    y: Math.min(Math.max(position.y, bounds.minY), bounds.maxY),
  };
}

export function midpoint(start: number, end: number) {
  return start + (end - start) / 2;
}
