# Current status

2026-10-26. Infra Canvas provides optional direct execution and Terrakube integration, with an independent Resources workspace.

- Kubernetes: six resource kinds, relationships, manual collection and partial failure handling.
- AWS: VPC, Subnet, SecurityGroup and EC2 inventory through a verified connection and restricted STS session.
- Durable observations, before/after comparisons, explicit resource-to-Canvas execution context.
- Kubernetes Events/status/restart signals and evidence-based rules/optional LLM analysis.
- Migration `0023_resource_observations` is required.

Local kind and PostgreSQL verification is separate from production verification. AWS SDK and LLM contract tests use mocks; no configured live AWS connection or LLM provider was used in this validation.

Automatic collection, IaC drift, import/adopt, Pod exec, automatic remediation and all-service AWS coverage remain outside this slice.

See [operations guide](RESOURCE-OPERATIONS.md), [deployment modes](DEPLOYMENT-MODES.md) and [Kubernetes setup](KUBERNETES-RESOURCES.md).
