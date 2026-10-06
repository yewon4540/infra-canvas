import { type ResourceCard } from "@/lib/canvas/kubernetesResourceMap";
import {
  midpoint,
  type NodeBounds,
} from "@/lib/canvas/kubernetesTopologyLayout";

const WORKLOAD_RESOURCE_COLUMNS: Partial<Record<string, number>> = {
  Ingress: 64,
  Service: 248,
  Deployment: 456,
  HPA: 456,
};

export type LaneResources = {
  traffic: ResourceCard[];
  controller: ResourceCard[];
  dependencies: ResourceCard[];
};

export function positionInLane(
  resource: ResourceCard,
  fallbackIndex: number,
  bounds: NodeBounds,
  laneResources: LaneResources,
  xOffset: number,
  workloadY?: number,
) {
  const workloadColumn = WORKLOAD_RESOURCE_COLUMNS[resource.kind];
  if (workloadY !== undefined && workloadColumn !== undefined) {
    return {
      x: xOffset + workloadColumn,
      y: resource.kind === "HPA" ? workloadY + 104 : workloadY,
    };
  }

  const lane = laneForResource(resource, laneResources);
  const laneIndex = lane.findIndex((item) => item.id === resource.id);
  const index = laneIndex >= 0 ? laneIndex : fallbackIndex;
  const count = Math.max(lane.length, 1);
  const x =
    count === 1
      ? midpoint(bounds.minX, bounds.maxX)
      : bounds.minX + ((bounds.maxX - bounds.minX) * index) / (count - 1);
  const rows = Math.max(Math.ceil(count / 3), 1);
  const row = Math.floor(index / 3);
  const centerY = midpoint(bounds.minY, bounds.maxY);
  const rowOffset = rows === 1 ? 0 : (row - (rows - 1) / 2) * 104;
  return { x, y: centerY + rowOffset };
}

function laneForResource(
  resource: ResourceCard,
  laneResources: LaneResources,
) {
  if (["Ingress", "Service", "EndpointSlice"].includes(resource.kind)) {
    return laneResources.traffic;
  }
  if (["ConfigMap", "SecretRef", "PVC"].includes(resource.kind)) {
    return laneResources.dependencies;
  }
  return laneResources.controller;
}
