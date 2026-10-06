import { type Edge, type Node } from "@xyflow/react";
import { getNodeTypeDef } from "@/lib/node-types";

export type KubeGroupId =
  | "scope"
  | "workloads"
  | "network"
  | "configuration"
  | "storage"
  | "rbac"
  | "policy";

export type ResourceCard = {
  id: string;
  kind: string;
  name: string;
  namespace: string;
  group: KubeGroupId;
  color: string;
  summary: string;
  properties: Record<string, unknown>;
  relations: string[];
  relationHints: Record<string, string | null>;
};

export type DiagramRelation = {
  source: ResourceCard;
  target: ResourceCard;
  label: string;
  inferred: boolean;
};

const TYPE_TO_KIND: Record<string, string> = {
  "kubernetes.namespace": "Namespace",
  "kubernetes.deployment": "Deployment",
  "kubernetes.service": "Service",
  "kubernetes.ingress": "Ingress",
  "kubernetes.config_map": "ConfigMap",
  "kubernetes.secret_ref": "SecretRef",
  "kubernetes.pvc": "PVC",
  "kubernetes.hpa": "HPA",
};

const TYPE_TO_GROUP: Record<string, KubeGroupId> = {
  "kubernetes.namespace": "scope",
  "kubernetes.deployment": "workloads",
  "kubernetes.service": "network",
  "kubernetes.ingress": "network",
  "kubernetes.config_map": "configuration",
  "kubernetes.secret_ref": "configuration",
  "kubernetes.pvc": "storage",
  "kubernetes.hpa": "policy",
};

export function buildResourceCards(nodes: Node[], edges: Edge[]): ResourceCard[] {
  const kubeNodes = nodes.filter((node) => node.type && TYPE_TO_KIND[node.type]);
  const cards = kubeNodes.map((node) => toResourceCard(node));
  const cardById = new Map(cards.map((card) => [card.id, card]));
  const cardByName = new Map(
    cards.map((card) => [`${card.namespace}:${card.name}`, card]),
  );

  for (const edge of edges) {
    const source = cardById.get(edge.source);
    const target = cardById.get(edge.target);
    if (!source || !target) continue;
    pushUnique(source.relations, `${target.kind}: ${target.name}`);
    pushUnique(target.relations, `${source.kind}: ${source.name}`);
  }
  for (const card of cards) {
    addInferredRelations(card, cardByName);
  }

  return cards.sort((a, b) => {
    const groupDiff = groupIndex(a.group) - groupIndex(b.group);
    if (groupDiff !== 0) return groupDiff;
    return a.name.localeCompare(b.name);
  });
}

export function buildDiagramRelations(
  resources: ResourceCard[],
  edges: Edge[],
): DiagramRelation[] {
  const resourceById = new Map(resources.map((resource) => [resource.id, resource]));
  const edgeRelations = edges
    .map((edge) => ({
      source: resourceById.get(edge.source),
      target: resourceById.get(edge.target),
      label: String(edge.data?.label || edge.type || "edge"),
      inferred: false,
    }))
    .filter(
      (edge): edge is DiagramRelation =>
        Boolean(edge.source && edge.target),
    );

  return dedupeRelations([
    ...buildInferredDiagramRelations(resources),
    ...edgeRelations,
  ]);
}

function toResourceCard(node: Node): ResourceCard {
  const props = (node.data?.properties as Record<string, unknown> | undefined) || {};
  const kind = TYPE_TO_KIND[node.type || ""] || "Resource";
  const name = cleanName(props.name || node.data?.display_name || node.data?.label || node.id);
  const namespace = kind === "Namespace" ? name : cleanName(props.namespace || "default");
  const def = getNodeTypeDef(node.type || "");
  return {
    id: node.id,
    kind,
    name,
    namespace,
    group: TYPE_TO_GROUP[node.type || ""] || "workloads",
    color: def?.color || "var(--color-text-muted)",
    summary: summaryFor(kind, props),
    properties: props,
    relations: [],
    relationHints: {
      service_name: cleanOptionalName(props.service_name),
      selector: cleanOptionalName(props.selector),
      target_deployment: cleanOptionalName(props.target_deployment),
    },
  };
}

function buildInferredDiagramRelations(resources: ResourceCard[]): DiagramRelation[] {
  const byName = new Map(
    resources.map((resource) => [`${resource.namespace}:${resource.name}`, resource]),
  );
  const relations: DiagramRelation[] = [];
  for (const resource of resources) {
    if (resource.kind === "Ingress") {
      const serviceName = relationValue(resource, "service_name") || resource.name;
      const service = byName.get(`${resource.namespace}:${serviceName}`);
      if (service) {
        relations.push({
          source: resource,
          target: service,
          label: "routes to",
          inferred: true,
        });
      }
    }
    if (resource.kind === "Service") {
      const selector = relationValue(resource, "selector") || resource.name;
      const deployment = byName.get(`${resource.namespace}:${selector}`);
      if (deployment?.kind === "Deployment") {
        relations.push({
          source: resource,
          target: deployment,
          label: "selects",
          inferred: true,
        });
      }
    }
    if (resource.kind === "HPA") {
      const target = relationValue(resource, "target_deployment") || resource.name;
      const deployment = byName.get(`${resource.namespace}:${target}`);
      if (deployment?.kind === "Deployment") {
        relations.push({
          source: resource,
          target: deployment,
          label: "scales",
          inferred: true,
        });
      }
    }
  }
  return relations;
}

function addInferredRelations(
  resource: ResourceCard,
  byName: Map<string, ResourceCard>,
) {
  if (resource.kind === "Ingress") {
    const serviceName = relationValue(resource, "service_name") || resource.name;
    const service = byName.get(`${resource.namespace}:${serviceName}`);
    if (service) {
      pushUnique(resource.relations, `Service: ${service.name}`);
      pushUnique(service.relations, `Ingress: ${resource.name}`);
    }
  }
  if (resource.kind === "Service") {
    const selector = relationValue(resource, "selector") || resource.name;
    const deployment = byName.get(`${resource.namespace}:${selector}`);
    if (deployment?.kind === "Deployment") {
      pushUnique(resource.relations, `Deployment: ${deployment.name}`);
      pushUnique(deployment.relations, `Service: ${resource.name}`);
    }
  }
  if (resource.kind === "HPA") {
    const target = relationValue(resource, "target_deployment") || resource.name;
    const deployment = byName.get(`${resource.namespace}:${target}`);
    if (deployment?.kind === "Deployment") {
      pushUnique(resource.relations, `Deployment: ${deployment.name}`);
      pushUnique(deployment.relations, `HPA: ${resource.name}`);
    }
  }
}

function dedupeRelations(relations: DiagramRelation[]): DiagramRelation[] {
  const seen = new Set<string>();
  const deduped: DiagramRelation[] = [];
  for (const relation of relations) {
    const key = `${relation.source.id}:${relation.target.id}:${relation.label}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(relation);
  }
  return deduped;
}

function relationValue(resource: ResourceCard, key: string): string | null {
  return resource.relationHints[key] || null;
}

function summaryFor(kind: string, props: Record<string, unknown>): string {
  if (kind === "Deployment") return `${props.replicas ?? 2} replicas · ${props.image || "nginx:1.27"}`;
  if (kind === "Service") return `${props.service_type || "ClusterIP"} · ${props.port || 80} -> ${props.target_port || props.port || 80}`;
  if (kind === "Ingress") return `${props.host || "host pending"}${props.path || "/"}`;
  if (kind === "ConfigMap") return "configuration data";
  if (kind === "SecretRef") return "existing Secret reference";
  if (kind === "PVC") return `${props.storage || "10Gi"} · ${props.access_mode || "ReadWriteOnce"}`;
  if (kind === "HPA") return `${props.min_replicas || 1}-${props.max_replicas || 5} replicas · CPU ${props.cpu_utilization || 70}%`;
  return "namespace scope";
}

function groupIndex(groupId: KubeGroupId): number {
  return GROUP_ORDER.indexOf(groupId);
}

function cleanName(value: unknown): string {
  const text = String(value || "resource").trim();
  return text || "resource";
}

function cleanOptionalName(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  const text = String(value).trim();
  return text || null;
}

function pushUnique(items: string[], item: string) {
  if (!items.includes(item)) items.push(item);
}

const GROUP_ORDER: KubeGroupId[] = [
  "scope",
  "workloads",
  "network",
  "configuration",
  "storage",
  "rbac",
  "policy",
];
