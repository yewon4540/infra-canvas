import { type ResourceCard } from "@/lib/canvas/kubernetesResourceMap";

export type RuntimeNode = {
  id: string;
  kind: string;
  name: string;
  namespace: string;
  status: string;
};

export function runtimeNode(
  resource: ResourceCard,
  kind: RuntimeNode["kind"],
): RuntimeNode {
  const replicas = Number(resource.properties.replicas || 2);
  const suffix =
    kind === "Pod" && resource.kind === "Deployment"
      ? `x${Number.isFinite(replicas) ? replicas : 2}`
      : kind === "ReplicaSet"
        ? "hash"
        : resource.name;
  return {
    id: `runtime-${kind}-${resource.id}`,
    kind,
    name: kind === "EndpointSlice" ? resource.name : `${resource.name}-${suffix}`,
    namespace: resource.namespace,
    status: kind === "EndpointSlice" ? "pending sync" : "dry-run 후 확인",
  };
}
