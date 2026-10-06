import { MarkerType, type Edge, type Node } from "@xyflow/react";
import { type ResourceCard } from "@/lib/canvas/kubernetesResourceMap";
import {
  boundsForResource,
  boundsWithin,
  clampPosition,
  NAMESPACE_GAP_X,
  NAMESPACE_WIDTH,
  TOPOLOGY_COLUMNS,
  TOPOLOGY_NODE_HEIGHT,
  type NodeBounds,
  WORKLOAD_ROW_GAP,
  GROUP_HEADER_HEIGHT,
} from "@/lib/canvas/kubernetesTopologyLayout";
import {
  hpaTargetsDeployment,
  ingressTargetsServices,
  isPrimaryResource,
  isSupportResource,
  resourceBelongsToDeployment,
  serviceTargetsDeployment,
} from "@/lib/canvas/kubernetesTopologyRelations";
import {
  runtimeNode,
  type RuntimeNode,
} from "@/lib/canvas/kubernetesTopologyRuntime";
import {
  positionInLane,
  type LaneResources,
} from "@/lib/canvas/kubernetesTopologyPlacement";

export { clampPosition };

export type GroupTone = "namespace" | "traffic" | "controller" | "dependencies";

export type TopologyNodeData = {
  kind: string;
  name: string;
  namespace?: string;
  status?: string;
  iconKind: string;
  tone?: GroupTone;
  bounds?: NodeBounds;
  selected?: boolean;
  virtual?: boolean;
  group?: boolean;
  onSelect?: (nodeId: string) => void;
};

export type TopologyBuildResult = {
  nodes: Node<TopologyNodeData>[];
  edges: Edge[];
};

export function buildKubernetesTopology(
  resources: ResourceCard[],
  selectedNodeId: string | null,
  onSelectNode: (nodeId: string) => void,
): TopologyBuildResult {
  const topologyNodes: Node<TopologyNodeData>[] = [];
  const topologyEdges: Edge[] = [];
  const namespaceNames = Array.from(
    new Set(resources.map((resource) => resource.namespace || "default")),
  ).sort();

  namespaceNames.forEach((namespace, namespaceIndex) => {
    const namespaceResources = resources.filter(
      (resource) => (resource.namespace || "default") === namespace,
    );
    const deployments = namespaceResources.filter(
      (resource) => resource.kind === "Deployment",
    );
    const namespaceNode =
      namespaceResources.find((resource) => resource.kind === "Namespace") ||
      null;
    const xOffset = namespaceIndex * NAMESPACE_GAP_X;
    const workloadRows = Math.max(deployments.length, 1);
    const laneHeight =
      GROUP_HEADER_HEIGHT +
      (workloadRows - 1) * WORKLOAD_ROW_GAP +
      TOPOLOGY_NODE_HEIGHT +
      144;
    const dependencyY = 88 + laneHeight + 48;
    const dependencyHeight =
      GROUP_HEADER_HEIGHT +
      (workloadRows - 1) * WORKLOAD_ROW_GAP +
      TOPOLOGY_NODE_HEIGHT +
      96;
    const orphanedCount = namespaceResources.filter(
      (resource) =>
        !isPrimaryResource(resource) &&
        !deployments.some((deployment) =>
          resourceBelongsToDeployment(resource, deployment, namespaceResources),
        ),
    ).length;
    const orphanedRows = Math.ceil(orphanedCount / 3);
    const namespaceHeight = Math.max(
      dependencyY + dependencyHeight + 56,
      220 + Math.max(orphanedRows, 1) * 104,
    );
    const namespaceBounds = boundsWithin(
      xOffset - 24,
      -28,
      NAMESPACE_WIDTH,
      namespaceHeight,
    );
    const trafficBounds = boundsWithin(xOffset + 16, 88, 584, laneHeight);
    const controllerBounds = boundsWithin(xOffset + 416, 88, 624, laneHeight);
    const dependencyBounds = boundsWithin(
      xOffset + 16,
      dependencyY,
      1000,
      dependencyHeight,
    );

    addGroupNode(
      topologyNodes,
      `group-${namespace}`,
      `Namespace / ${namespace}`,
      xOffset - 24,
      -28,
      NAMESPACE_WIDTH,
      namespaceHeight,
      "namespace",
    );
    addGroupNode(
      topologyNodes,
      `group-${namespace}-traffic`,
      "Traffic",
      xOffset + 16,
      88,
      584,
      laneHeight,
      "traffic",
    );
    addGroupNode(
      topologyNodes,
      `group-${namespace}-controller`,
      "Controller",
      xOffset + 416,
      88,
      624,
      laneHeight,
      "controller",
    );
    addGroupNode(
      topologyNodes,
      `group-${namespace}-deps`,
      "Dependencies",
      xOffset + 16,
      dependencyY,
      1000,
      dependencyHeight,
      "dependencies",
    );

    addNode(
      topologyNodes,
      namespaceNode
        ? toResourceNode(namespaceNode, selectedNodeId, onSelectNode, namespaceBounds)
        : toVirtualNode(
            `virtual-ns-${namespace}`,
            "Namespace",
            namespace,
            namespace,
            namespaceBounds,
          ),
      xOffset,
      0,
    );

    deployments.forEach((deployment, index) => {
      const y = 160 + index * WORKLOAD_ROW_GAP;
      const services = namespaceResources.filter((resource) =>
        serviceTargetsDeployment(resource, deployment),
      );
      const ingresses = namespaceResources.filter((resource) =>
        ingressTargetsServices(resource, services),
      );
      const hpas = namespaceResources.filter((resource) =>
        hpaTargetsDeployment(resource, deployment),
      );
      const support = namespaceResources.filter((resource) =>
        isSupportResource(resource),
      );
      const replicaSet = runtimeNode(deployment, "ReplicaSet");
      const pod = runtimeNode(deployment, "Pod");
      const endpoint = services[0]
        ? runtimeNode(services[0], "EndpointSlice")
        : null;

      addResourceNodes(
        topologyNodes,
        [...ingresses, ...services, deployment, ...hpas],
        selectedNodeId,
        onSelectNode,
        {
          traffic: trafficBounds,
          controller: controllerBounds,
          dependencies: dependencyBounds,
        },
        xOffset,
        y,
      );
      addResourceNodes(
        topologyNodes,
        support,
        selectedNodeId,
        onSelectNode,
        {
          traffic: trafficBounds,
          controller: controllerBounds,
          dependencies: dependencyBounds,
        },
        xOffset,
      );
      addRuntimeNode(
        topologyNodes,
        replicaSet,
        xOffset + TOPOLOGY_COLUMNS.replicaSet,
        y,
        controllerBounds,
      );
      addRuntimeNode(
        topologyNodes,
        pod,
        xOffset + TOPOLOGY_COLUMNS.pod,
        y,
        controllerBounds,
      );
      if (endpoint) {
        addRuntimeNode(
          topologyNodes,
          endpoint,
          xOffset + TOPOLOGY_COLUMNS.endpoint,
          y,
          trafficBounds,
        );
      }

      for (const ingress of ingresses) {
        for (const service of services) addEdge(topologyEdges, ingress.id, service.id);
      }
      for (const service of services) {
        if (endpoint) addEdge(topologyEdges, service.id, endpoint.id);
        addEdge(topologyEdges, endpoint?.id || service.id, pod.id);
      }
      for (const hpa of hpas) addEdge(topologyEdges, hpa.id, deployment.id);
      addEdge(topologyEdges, deployment.id, replicaSet.id);
      addEdge(topologyEdges, replicaSet.id, pod.id);
      for (const resource of support) addEdge(topologyEdges, resource.id, deployment.id);
    });

    const assigned = new Set<string>(deployments.map((deployment) => deployment.id));
    for (const deployment of deployments) {
      for (const resource of namespaceResources) {
        if (
          serviceTargetsDeployment(resource, deployment) ||
          hpaTargetsDeployment(resource, deployment) ||
          isSupportResource(resource)
        ) {
          assigned.add(resource.id);
        }
      }
      for (const ingress of namespaceResources.filter((r) => r.kind === "Ingress")) {
        const services = namespaceResources.filter((resource) =>
          serviceTargetsDeployment(resource, deployment),
        );
        if (ingressTargetsServices(ingress, services)) assigned.add(ingress.id);
      }
    }
    if (namespaceNode) assigned.add(namespaceNode.id);
    namespaceResources
      .filter((resource) => !assigned.has(resource.id))
      .forEach((resource, index) => {
        addNode(
          topologyNodes,
          toResourceNode(resource, selectedNodeId, onSelectNode, namespaceBounds),
          xOffset + 40 + (index % 3) * 200,
          120 + Math.floor(index / 3) * 95,
        );
      });
  });

  return { nodes: topologyNodes, edges: topologyEdges };
}

function addResourceNodes(
  nodes: Node<TopologyNodeData>[],
  resources: ResourceCard[],
  selectedNodeId: string | null,
  onSelectNode: (nodeId: string) => void,
  bounds: {
    traffic: NodeBounds;
    controller: NodeBounds;
    dependencies: NodeBounds;
  },
  xOffset: number,
  workloadY?: number,
) {
  const laneResources: LaneResources = {
    traffic: resources.filter((resource) =>
      ["Ingress", "Service", "EndpointSlice"].includes(resource.kind),
    ),
    controller: resources.filter(
      (resource) =>
        !["Ingress", "Service", "EndpointSlice", "ConfigMap", "SecretRef", "PVC"].includes(
          resource.kind,
        ),
    ),
    dependencies: resources.filter((resource) =>
      ["ConfigMap", "SecretRef", "PVC"].includes(resource.kind),
    ),
  };
  resources.forEach((resource, index) => {
    const resourceBounds = boundsForResource(resource, bounds);
    const position = positionInLane(
      resource,
      index,
      resourceBounds,
      laneResources,
      xOffset,
      workloadY,
    );
    addNode(
      nodes,
      toResourceNode(resource, selectedNodeId, onSelectNode, resourceBounds),
      position.x,
      position.y,
    );
  });
}

function addGroupNode(
  nodes: Node<TopologyNodeData>[],
  id: string,
  name: string,
  x: number,
  y: number,
  width: number,
  height: number,
  tone: GroupTone,
) {
  if (nodes.some((item) => item.id === id)) return;
  nodes.push({
    id,
    type: "kubeGroup",
    selectable: false,
    draggable: false,
    position: { x, y },
    style: { width, height, zIndex: -1 },
    data: {
      kind: "Group",
      iconKind: "Namespace",
      name,
      tone,
      group: true,
    },
  });
}

function addNode(
  nodes: Node<TopologyNodeData>[],
  node: Node<TopologyNodeData>,
  x: number,
  y: number,
) {
  if (nodes.some((item) => item.id === node.id)) return;
  nodes.push({ ...node, position: { x, y } });
}

function addRuntimeNode(
  nodes: Node<TopologyNodeData>[],
  runtime: RuntimeNode,
  x: number,
  y: number,
  bounds: NodeBounds,
) {
  addNode(
    nodes,
    {
      id: runtime.id,
      type: "kubeTopology",
      data: {
        kind: runtime.kind,
        iconKind: runtime.kind,
        name: runtime.name,
        namespace: runtime.namespace,
        status: runtime.status,
        bounds,
        virtual: true,
      },
      position: { x, y },
    },
    x,
    y,
  );
}

function toResourceNode(
  resource: ResourceCard,
  selectedNodeId: string | null,
  onSelectNode: (nodeId: string) => void,
  bounds: NodeBounds,
): Node<TopologyNodeData> {
  return {
    id: resource.id,
    type: "kubeTopology",
    position: { x: 0, y: 0 },
    data: {
      kind: resource.kind,
      iconKind: resource.kind,
      name: resource.name,
      namespace: resource.namespace,
      bounds,
      selected: selectedNodeId === resource.id,
      onSelect: onSelectNode,
    },
  };
}

function toVirtualNode(
  id: string,
  kind: string,
  name: string,
  namespace: string,
  bounds: NodeBounds,
): Node<TopologyNodeData> {
  return {
    id,
    type: "kubeTopology",
    position: { x: 0, y: 0 },
    data: {
      kind,
      iconKind: kind,
      name,
      namespace,
      bounds,
      virtual: true,
    },
  };
}

function addEdge(edges: Edge[], source: string, target: string) {
  if (!source || !target || source === target) return;
  const id = `${source}->${target}`;
  if (edges.some((edge) => edge.id === id)) return;
  edges.push({
    id,
    source,
    target,
    type: "smoothstep",
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: "var(--color-border-strong)", strokeWidth: 2.1 },
  });
}
