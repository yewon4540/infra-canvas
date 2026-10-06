"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  createTarget,
  getKubernetesReadOnlyManifest,
  listAwsConnections,
  listEnvironments,
  listTargets,
  verifyTarget,
  type AwsConnection,
  type Environment,
  type KubernetesReadOnlyManifest,
  type Target,
  type TargetKind,
  type TargetVerifyResult,
} from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";

const KIND_LABELS: Record<TargetKind, string> = {
  aws_account: "AWS Account",
  kubernetes_cluster: "Kubernetes Cluster",
};

export default function TargetsPage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [awsConnections, setAwsConnections] = useState<AwsConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<TargetKind>("kubernetes_cluster");
  const [environmentId, setEnvironmentId] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [awsConnectionId, setAwsConnectionId] = useState("");
  const [namespace, setNamespace] = useState("");
  const [secretName, setSecretName] = useState("");
  const [tokenEnv, setTokenEnv] = useState("");
  const [caCertEnv, setCaCertEnv] = useState("");
  const [endpointEnv, setEndpointEnv] = useState("");
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);
  const [readOnlyManifest, setReadOnlyManifest] =
    useState<KubernetesReadOnlyManifest | null>(null);
  const [verifyResults, setVerifyResults] = useState<
    Record<string, TargetVerifyResult>
  >({});

  useEffect(() => {
    Promise.all([listTargets(), listEnvironments(), listAwsConnections()])
      .then(([targetList, environmentList, connectionList]) => {
        setTargets(targetList);
        setEnvironments(environmentList);
        setAwsConnections(connectionList);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    if (kind === "kubernetes_cluster" && !endpoint.trim()) return;
    if (kind === "aws_account" && !awsConnectionId) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createTarget({
        name: name.trim(),
        kind,
        provider: kind === "aws_account" ? "aws" : "kubernetes",
        environment_id: environmentId || null,
        aws_connection_id: kind === "aws_account" ? awsConnectionId : null,
        endpoint: kind === "kubernetes_cluster" ? endpoint.trim() : null,
        config:
          kind === "kubernetes_cluster" && namespace.trim()
            ? { default_namespace: namespace.trim() }
            : {},
        secret_ref:
          kind === "kubernetes_cluster" && secretName.trim()
            ? {
                backend: tokenEnv.trim() && caCertEnv.trim() ? "env" : "unconfigured",
                type: "service_account",
                name: secretName.trim(),
                token_env: tokenEnv.trim() || undefined,
                ca_cert_env: caCertEnv.trim() || undefined,
                endpoint_env: endpointEnv.trim() || undefined,
              }
            : null,
      });
      setTargets((prev) => [created, ...prev]);
      setName("");
      setEndpoint("");
      setAwsConnectionId("");
      setNamespace("");
      setSecretName("");
      setTokenEnv("");
      setCaCertEnv("");
      setEndpointEnv("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCreating(false);
    }
  }

  async function handleVerify(target: Target) {
    setVerifyingId(target.id);
    setError(null);
    try {
      const result = await verifyTarget(target.id);
      setVerifyResults((current) => ({ ...current, [target.id]: result }));
      setTargets((current) =>
        current.map((item) =>
          item.id === target.id
            ? {
                ...item,
                status: result.status,
                last_verified_at: result.last_verified_at || item.last_verified_at,
                last_error: result.ok ? null : result.message,
              }
            : item,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVerifyingId(null);
    }
  }

  async function handleLoadManifest() {
    setManifestLoading(true);
    setError(null);
    try {
      setReadOnlyManifest(await getKubernetesReadOnlyManifest());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setManifestLoading(false);
    }
  }

  const canSubmit =
    Boolean(name.trim()) &&
    (kind === "kubernetes_cluster" ? Boolean(endpoint.trim()) : Boolean(awsConnectionId));

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-10">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <Link
            href="/settings"
            className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:underline"
          >
            환경설정
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--color-text)]">
            Targets
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            AWS Account와 Kubernetes Cluster를 공통 운영 대상으로 관리합니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <UserMenu />
          <ThemeToggle />
        </div>
      </div>

      <form
        onSubmit={handleCreate}
        className="mb-5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]"
      >
        <div className="grid gap-3 border-b border-[var(--color-border)] p-4 lg:grid-cols-[1fr_220px_220px_auto]">
          <Field label="Name">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="target name"
              className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
            />
          </Field>
          <Field label="Kind">
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as TargetKind)}
              className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
            >
              <option value="kubernetes_cluster">Kubernetes Cluster</option>
              <option value="aws_account">AWS Account</option>
            </select>
          </Field>
          <Field label="Environment">
            <select
              value={environmentId}
              onChange={(event) => setEnvironmentId(event.target.value)}
              className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
            >
              <option value="">미지정</option>
              {environments.map((environment) => (
                <option key={environment.id} value={environment.id}>
                  {environment.slug} · {environment.risk_level}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={creating || !canSubmit}
              className="h-10 rounded-md bg-[var(--color-accent)] px-4 text-sm font-medium text-[var(--color-accent-fg)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {creating ? "생성 중" : "Target 생성"}
            </button>
          </div>
        </div>

        <div className="grid gap-3 p-4 lg:grid-cols-3">
          {kind === "kubernetes_cluster" ? (
            <>
              <Field label="Kubernetes API Endpoint">
                <input
                  value={endpoint}
                  onChange={(event) => setEndpoint(event.target.value)}
                  placeholder="https://kubernetes.example.com:6443"
                  className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
                />
              </Field>
              <Field label="Default Namespace">
                <input
                  value={namespace}
                  onChange={(event) => setNamespace(event.target.value)}
                  placeholder="default"
                  className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
                />
              </Field>
              <Field label="Secret Reference">
                <input
                  value={secretName}
                  onChange={(event) => setSecretName(event.target.value)}
                  placeholder="eolgae-reader-prod"
                  className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
                />
                <span className="mt-1 block text-[11px] leading-relaxed text-[var(--color-text-subtle)]">
                  ServiceAccount credential reference 이름입니다.
                </span>
              </Field>
              <Field label="Token Env Key">
                <input
                  value={tokenEnv}
                  onChange={(event) => setTokenEnv(event.target.value)}
                  placeholder="EOLGAE_KUBE_TOKEN_PROD"
                  className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
                />
              </Field>
              <Field label="CA Cert Env Key">
                <input
                  value={caCertEnv}
                  onChange={(event) => setCaCertEnv(event.target.value)}
                  placeholder="EOLGAE_KUBE_CA_PROD"
                  className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
                />
              </Field>
              <Field label="Endpoint Env Key">
                <input
                  value={endpointEnv}
                  onChange={(event) => setEndpointEnv(event.target.value)}
                  placeholder="optional"
                  className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
                />
                <span className="mt-1 block text-[11px] leading-relaxed text-[var(--color-text-subtle)]">
                  값이 비어 있으면 위 API endpoint를 사용합니다.
                </span>
              </Field>
            </>
          ) : (
            <Field label="AWS Connection">
              <select
                value={awsConnectionId}
                onChange={(event) => setAwsConnectionId(event.target.value)}
                className="h-10 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none"
              >
                <option value="">AWS Connection 선택</option>
                {awsConnections.map((connection) => (
                  <option key={connection.id} value={connection.id}>
                    {connection.name} · {connection.account_id} / {connection.default_region}
                  </option>
                ))}
              </select>
            </Field>
          )}
        </div>
        {kind === "kubernetes_cluster" && (
          <div className="border-t border-[var(--color-border)] p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-[var(--color-text)]">
                  Read-only ServiceAccount 연결
                </h2>
                <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[var(--color-text-muted)]">
                  클러스터에는 조회 전용 RBAC만 적용하고, 발급한 token/CA/API endpoint는
                  Eolgae secret backend에 저장한 뒤 위 Secret Reference로 연결합니다.
                </p>
              </div>
              <button
                type="button"
                onClick={handleLoadManifest}
                disabled={manifestLoading}
                className="h-9 shrink-0 rounded-md border border-[var(--color-border)] px-3 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {manifestLoading ? "불러오는 중" : "RBAC Manifest 보기"}
              </button>
            </div>
            {readOnlyManifest && (
              <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,24rem)]">
                <pre className="max-h-80 overflow-auto rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-xs leading-relaxed text-[var(--color-text)]">
                  {readOnlyManifest.manifest}
                </pre>
                <div className="rounded border border-[var(--color-border)] bg-[var(--color-bg)] p-3 text-xs text-[var(--color-text-muted)]">
                  <div className="font-semibold text-[var(--color-text)]">연결 순서</div>
                  <CommandLine label="1. RBAC 적용" value={readOnlyManifest.apply_command} />
                  <CommandLine label="2. Token 발급" value={readOnlyManifest.token_command} />
                  <CommandLine label="3. CA 조회" value={readOnlyManifest.ca_command} />
                  <CommandLine label="4. API endpoint 조회" value={readOnlyManifest.endpoint_command} />
                </div>
              </div>
            )}
          </div>
        )}
      </form>

      {error && <p className="mb-4 text-sm text-[var(--color-danger)]">{error}</p>}

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">로딩 중...</p>
      ) : targets.length === 0 ? (
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-10 text-center text-sm text-[var(--color-text-muted)]">
          등록된 target이 없습니다.
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-[var(--color-bg-subtle)] text-left text-xs font-medium uppercase text-[var(--color-text-subtle)]">
              <tr>
                <th className="px-4 py-2">Target</th>
                <th className="px-4 py-2">Kind</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Endpoint / Connection</th>
                <th className="px-4 py-2">Verification</th>
                <th className="px-4 py-2">Updated</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((target) => (
                <tr
                  key={target.id}
                  className="border-t border-[var(--color-border)]"
                >
                  <td className="px-4 py-3">
                    <div className="font-semibold text-[var(--color-text)]">
                      {target.name}
                    </div>
                    <div className="mt-0.5 text-xs text-[var(--color-text-subtle)]">
                      {target.slug}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">
                    {KIND_LABELS[target.kind]}
                  </td>
                  <td className="px-4 py-3">
                    <span className={statusClass(target.status)}>
                      {target.status}
                    </span>
                    {target.last_verified_at && (
                      <div className="mt-1 text-[11px] text-[var(--color-text-subtle)]">
                        verified {new Date(target.last_verified_at).toLocaleString("ko-KR")}
                      </div>
                    )}
                    {target.last_error && (
                      <div className="mt-1 max-w-[12rem] truncate text-[11px] text-[var(--color-danger)]">
                        {target.last_error}
                      </div>
                    )}
                  </td>
                  <td className="max-w-[24rem] truncate px-4 py-3 text-[var(--color-text-muted)]">
                    <div className="truncate">
                      {target.kind === "aws_account"
                        ? target.aws_connection_id || "-"
                        : target.endpoint || "-"}
                    </div>
                    {target.kind === "kubernetes_cluster" && target.secret_ref && (
                      <div className="mt-1 truncate text-[11px] text-[var(--color-text-subtle)]">
                        secret {String(target.secret_ref.name || "-")} ·{" "}
                        {String(target.secret_ref.backend || target.secret_ref.type || "unconfigured")}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleVerify(target)}
                      disabled={verifyingId === target.id}
                      className="rounded-md border border-[var(--color-border)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {verifyingId === target.id ? "검증 중" : "Verify"}
                    </button>
                    {verifyResults[target.id] && (
                      <div className="mt-2 max-w-[18rem] text-[11px] leading-relaxed text-[var(--color-text-muted)]">
                        <div className={verificationMessageClass(verifyResults[target.id])}>
                          {verifyResults[target.id].message}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {verifyResults[target.id].checks.map((check) => (
                            <span
                              key={check.name}
                              title={check.message}
                              className={
                                check.ok
                                  ? "rounded bg-[var(--color-success)]/10 px-1.5 py-0.5 text-[var(--color-success)]"
                                  : "rounded bg-[var(--color-danger)]/10 px-1.5 py-0.5 text-[var(--color-danger)]"
                              }
                            >
                              {check.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--color-text-muted)]">
                    {new Date(target.updated_at).toLocaleString("ko-KR")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

function CommandLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-3">
      <div className="mb-1 text-[11px] font-medium text-[var(--color-text-subtle)]">
        {label}
      </div>
      <code className="block rounded bg-[var(--color-bg-subtle)] px-2 py-1.5 text-[11px] leading-relaxed text-[var(--color-text)]">
        {value}
      </code>
    </div>
  );
}

function statusClass(status: Target["status"]): string {
  if (status === "ready") {
    return "rounded bg-[var(--color-success)]/10 px-2 py-0.5 text-xs font-medium text-[var(--color-success)]";
  }
  if (status === "error") {
    return "rounded bg-[var(--color-danger)]/10 px-2 py-0.5 text-xs font-medium text-[var(--color-danger)]";
  }
  if (status === "pending") {
    return "rounded bg-[var(--color-warning)]/10 px-2 py-0.5 text-xs font-medium text-[var(--color-warning)]";
  }
  return "rounded bg-[var(--color-bg-subtle)] px-2 py-0.5 text-xs font-medium text-[var(--color-text-muted)]";
}

function verificationMessageClass(result: TargetVerifyResult): string {
  if (result.ok) return "text-[var(--color-success)]";
  if (result.status === "pending") return "text-[var(--color-warning)]";
  return "text-[var(--color-danger)]";
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
        {label}
      </span>
      {children}
    </label>
  );
}
