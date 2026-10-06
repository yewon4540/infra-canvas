"use client";

import { type Edge, type Node } from "@xyflow/react";
import { getNodeTypeDef } from "@/lib/node-types";

type KubeResourceKind =
  | "Namespace"
  | "Deployment"
  | "Service"
  | "Ingress"
  | "ConfigMap"
  | "SecretRef"
  | "PVC"
  | "HPA";

type KubeResource = {
  id: string;
  type: string;
  kind: KubeResourceKind;
  name: string;
  namespace: string;
  color: string;
  summary: string;
  relations: string[];
  relationHints: Record<string, string>;
};

type NamespaceGroup = {
  name: string;
  resources: KubeResource[];
};

const KIND_BY_TYPE: Record<string, KubeResourceKind> = {
  "kubernetes.namespace": "Namespace",
  "kubernetes.deployment": "Deployment",
  "kubernetes.service": "Service",
  "kubernetes.ingress": "Ingress",
  "kubernetes.config_map": "ConfigMap",
  "kubernetes.secret_ref": "SecretRef",
  "kubernetes.pvc": "PVC",
  "kubernetes.hpa": "HPA",
};

const KIND_ORDER: Record<KubeResourceKind, number> = {
  Namespace: 0,
  Ingress: 1,
  Service: 2,
  Deployment: 3,
  HPA: 4,
  ConfigMap: 5,
  SecretRef: 6,
  PVC: 7,
};

export function KubernetesResourceTree({
  nodes,
  edges,
  onClose,
  onSelectNode,
}: {
  nodes: Node[];
  edges: Edge[];
  onClose: () => void;
  onSelectNode?: (nodeId: string) => void;
}) {
  const resources = buildResources(nodes, edges);
  const groups = groupByNamespace(resources);
  const total = resources.length;

  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--color-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2">
        <div>
          <div className="text-sm font-semibold text-[var(--color-text)]">
            Kubernetes Resources
          </div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            Preview only · {total} resources
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="닫기"
          className="rounded px-2 py-1 text-sm text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
        >
          ✕
        </button>
      </div>

      {groups.length === 0 ? (
        <div className="p-5 text-sm leading-relaxed text-[var(--color-text-muted)]">
          Kubernetes 리소스가 없습니다. 팔레트에서 Namespace, Deployment, Service 등을 추가하면 여기에서 구조를 볼 수 있습니다.
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <div className="mb-3 grid grid-cols-3 gap-2">
            <Metric label="Namespace" value={countKind(resources, "Namespace")} />
            <Metric label="Workload" value={countKind(resources, "Deployment")} />
            <Metric label="Route" value={countKind(resources, "Ingress") + countKind(resources, "Service")} />
          </div>
          <div className="space-y-3">
            {groups.map((group) => (
              <section
                key={group.name}
                className="border border-[var(--color-border)] bg-[var(--color-surface)]"
              >
                <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                      Namespace
                    </div>
                    <div className="truncate text-sm font-semibold text-[var(--color-text)]">
                      {group.name}
                    </div>
                  </div>
                  <span className="rounded bg-[var(--color-surface)] px-2 py-1 text-[11px] text-[var(--color-text-muted)]">
                    {group.resources.length}
                  </span>
                </div>
                <div className="divide-y divide-[var(--color-border)]">
                  {group.resources.map((resource) => (
                    <ResourceRow
                      key={resource.id}
                      resource={resource}
                      onSelectNode={onSelectNode}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-subtle)]">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold text-[var(--color-text)]">
        {value}
      </div>
    </div>
  );
}

function ResourceRow({
  resource,
  onSelectNode,
}: {
  resource: KubeResource;
  onSelectNode?: (nodeId: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSelectNode?.(resource.id)}
      className="block w-full px-3 py-2.5 text-left hover:bg-[var(--color-bg-subtle)]"
    >
      <div className="flex items-start gap-2">
        <span
          className="mt-1 h-2 w-2 shrink-0 rounded-full"
          style={{ background: resource.color }}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="shrink-0 rounded bg-[var(--color-bg-subtle)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              {resource.kind}
            </span>
            <span className="truncate text-sm font-semibold text-[var(--color-text)]">
              {resource.name}
            </span>
          </div>
          <div className="mt-1 truncate text-xs text-[var(--color-text-muted)]">
            {resource.summary}
          </div>
          {resource.relations.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {resource.relations.map((relation) => (
                <span
                  key={relation}
                  className="rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[10px] text-[var(--color-accent)]"
                >
                  {relation}
                </span>
              ))}
            </div>
          )}
        </div>
        <span className="shrink-0 rounded border border-[var(--color-border)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-subtle)]">
          Unknown
        </span>
      </div>
    </button>
  );
}

function buildResources(nodes: Node[], edges: Edge[]): KubeResource[] {
  const kubeNodes = nodes.filter((node) => node.type && KIND_BY_TYPE[node.type]);
  const byId = new Map(kubeNodes.map((node) => [node.id, node]));
  const resources = kubeNodes.map((node) => toResource(node));
  const byName = new Map(
    resources.map((resource) => [
      `${resource.namespace}:${resource.name}`,
      resource,
    ]),
  );

  for (const resource of resources) {
    addInferredRelations(resource, byName);
  }

  for (const edge of edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;
    const sourceResource = resources.find((item) => item.id === source.id);
    const targetResource = resources.find((item) => item.id === target.id);
    if (!sourceResource || !targetResource) continue;
    pushUnique(sourceResource.relations, `${targetResource.kind}: ${targetResource.name}`);
    pushUnique(targetResource.relations, `${sourceResource.kind}: ${sourceResource.name}`);
  }

  return resources.sort((a, b) => {
    const kindDiff = KIND_ORDER[a.kind] - KIND_ORDER[b.kind];
    if (kindDiff !== 0) return kindDiff;
    return a.name.localeCompare(b.name);
  });
}

function toResource(node: Node): KubeResource {
  const props = (node.data?.properties as Record<string, unknown> | undefined) || {};
  const kind = KIND_BY_TYPE[node.type || ""] || "Deployment";
  const def = getNodeTypeDef(node.type || "");
  const name = cleanName(
    props.name ||
      node.data?.display_name ||
      node.data?.label ||
      node.id,
  );
  const namespace =
    kind === "Namespace"
      ? name
      : cleanName(props.namespace || "default");

  return {
    id: node.id,
    type: node.type || "",
    kind,
    name,
    namespace,
    color: def?.color || "var(--color-text-muted)",
    summary: summaryFor(kind, props),
    relations: [],
    relationHints: {
      service_name: cleanOptionalName(props.service_name),
      selector: cleanOptionalName(props.selector),
      target_deployment: cleanOptionalName(props.target_deployment),
    },
  };
}

function addInferredRelations(
  resource: KubeResource,
  byName: Map<string, KubeResource>,
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

function relationValue(resource: KubeResource, key: string): string | null {
  return resource.relationHints[key] || null;
}

function groupByNamespace(resources: KubeResource[]): NamespaceGroup[] {
  const groups = new Map<string, KubeResource[]>();
  for (const resource of resources) {
    const key = resource.namespace || "default";
    const current = groups.get(key) || [];
    current.push(resource);
    groups.set(key, current);
  }
  return Array.from(groups.entries())
    .map(([name, items]) => ({ name, resources: items }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function summaryFor(kind: KubeResourceKind, props: Record<string, unknown>): string {
  if (kind === "Deployment") {
    return `${props.replicas ?? 2} replicas · ${props.image || "nginx:1.27"}`;
  }
  if (kind === "Service") {
    return `${props.service_type || "ClusterIP"} · ${props.port || 80} -> ${props.target_port || props.port || 80}`;
  }
  if (kind === "Ingress") {
    return `${props.host || "host pending"}${props.path || "/"}`;
  }
  if (kind === "ConfigMap") return "configuration data";
  if (kind === "SecretRef") return "existing Secret reference";
  if (kind === "PVC") return `${props.storage || "10Gi"} · ${props.access_mode || "ReadWriteOnce"}`;
  if (kind === "HPA") return `${props.min_replicas || 1}-${props.max_replicas || 5} replicas · CPU ${props.cpu_utilization || 70}%`;
  return "namespace scope";
}

function countKind(resources: KubeResource[], kind: KubeResourceKind): number {
  return resources.filter((resource) => resource.kind === kind).length;
}

function cleanName(value: unknown): string {
  const text = String(value || "resource").trim();
  return text || "resource";
}

function cleanOptionalName(value: unknown): string {
  return String(value || "").trim();
}

function pushUnique(items: string[], item: string) {
  if (!items.includes(item)) items.push(item);
}
