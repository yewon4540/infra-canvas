import { type ResourceCard } from "@/lib/canvas/kubernetesResourceMap";

export function serviceTargetsDeployment(
  service: ResourceCard,
  deployment: ResourceCard,
) {
  if (service.kind !== "Service") return false;
  const selector = String(service.properties.selector || service.name);
  return service.namespace === deployment.namespace && selector === deployment.name;
}

export function ingressTargetsServices(
  ingress: ResourceCard,
  services: ResourceCard[],
) {
  if (ingress.kind !== "Ingress") return false;
  const serviceName = String(ingress.properties.service_name || ingress.name);
  return services.some(
    (service) =>
      service.namespace === ingress.namespace && service.name === serviceName,
  );
}

export function hpaTargetsDeployment(hpa: ResourceCard, deployment: ResourceCard) {
  if (hpa.kind !== "HPA") return false;
  const target = String(hpa.properties.target_deployment || hpa.name);
  return hpa.namespace === deployment.namespace && target === deployment.name;
}

export function isSupportResource(resource: ResourceCard) {
  return ["ConfigMap", "SecretRef", "PVC"].includes(resource.kind);
}

export function isPrimaryResource(resource: ResourceCard) {
  return resource.kind === "Namespace" || resource.kind === "Deployment";
}

export function resourceBelongsToDeployment(
  resource: ResourceCard,
  deployment: ResourceCard,
  namespaceResources: ResourceCard[],
) {
  if (
    serviceTargetsDeployment(resource, deployment) ||
    hpaTargetsDeployment(resource, deployment) ||
    isSupportResource(resource)
  ) {
    return true;
  }
  const services = namespaceResources.filter((service) =>
    serviceTargetsDeployment(service, deployment),
  );
  return ingressTargetsServices(resource, services);
}
