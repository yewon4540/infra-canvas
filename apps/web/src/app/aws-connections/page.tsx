"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  ApiError,
  listAwsConnections,
  prepareAwsConnection,
  saveAwsConnectionRole,
  verifyAwsConnection,
  type AwsConnection,
} from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";

export default function AwsConnectionsPage() {
  const [connections, setConnections] = useState<AwsConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [accountId, setAccountId] = useState("");
  const [region, setRegion] = useState("ap-northeast-2");
  const [busy, setBusy] = useState<string | null>(null);
  const [roleInputs, setRoleInputs] = useState<Record<string, string>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    listAwsConnections()
      .then((items) => {
        setConnections(items);
        setRoleInputs(
          Object.fromEntries(items.map((item) => [item.id, item.role_arn || ""])),
        );
      })
      .catch((exc) => setError(asMessage(exc)))
      .finally(() => setLoading(false));
  }, []);

  async function handlePrepare(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{12}$/.test(accountId)) return;
    setBusy("prepare");
    setError(null);
    setNotice(null);
    try {
      const prepared = await prepareAwsConnection({ account_id: accountId, region });
      upsertConnection(prepared);
      setRoleInputs((prev) => ({
        ...prev,
        [prepared.id]: prepared.role_arn || prev[prepared.id] || "",
      }));
      setExpandedId(prepared.id);
      setNotice("AWS 연결 준비가 완료되었습니다.");
    } catch (exc) {
      setError(asMessage(exc));
    } finally {
      setBusy(null);
    }
  }

  async function handleSaveRole(connection: AwsConnection) {
    const roleArn = roleInputs[connection.id]?.trim();
    if (!roleArn) return;
    setBusy(`role:${connection.id}`);
    setError(null);
    setNotice(null);
    try {
      const updated = await saveAwsConnectionRole(connection.id, roleArn);
      upsertConnection(updated);
      setNotice("Role ARN을 저장했습니다.");
    } catch (exc) {
      setError(asMessage(exc));
    } finally {
      setBusy(null);
    }
  }

  async function handleVerify(connection: AwsConnection) {
    setBusy(`verify:${connection.id}`);
    setError(null);
    setNotice(null);
    try {
      const result = await verifyAwsConnection(connection.id);
      const refreshed = await listAwsConnections();
      setConnections(refreshed);
      setRoleInputs(
        Object.fromEntries(
          refreshed.map((item) => [item.id, roleInputs[item.id] || item.role_arn || ""]),
        ),
      );
      if (result.ok) {
        setNotice(result.message || "AWS 연결 검증이 완료되었습니다.");
      } else {
        setError(result.message);
      }
    } catch (exc) {
      setError(asMessage(exc));
    } finally {
      setBusy(null);
    }
  }

  async function copy(text: string, key: string) {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    window.setTimeout(() => setCopied(null), 1500);
  }

  function upsertConnection(connection: AwsConnection) {
    setConnections((prev) => {
      const exists = prev.some((item) => item.id === connection.id);
      if (exists) {
        return prev.map((item) => (item.id === connection.id ? connection : item));
      }
      return [connection, ...prev];
    });
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link
            href="/settings"
            className="text-sm hover:underline"
            style={{ color: "var(--color-accent)" }}
          >
            환경설정
          </Link>
          <h1
            className="mt-1 text-2xl font-bold tracking-tight"
            style={{ color: "var(--color-text)" }}
          >
            AWS Connections
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>
            Project Group과 Canvas에서 사용할 AWS 계정 Role 연결을 관리합니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <UserMenu />
          <ThemeToggle />
        </div>
      </div>

      <form
        onSubmit={handlePrepare}
        className="mb-5 grid gap-3 rounded-md border p-3 md:grid-cols-[1fr_180px_auto]"
        style={{
          background: "var(--color-surface)",
          borderColor: "var(--color-border)",
        }}
      >
        <input
          value={accountId}
          onChange={(event) =>
            setAccountId(event.target.value.replace(/\D/g, "").slice(0, 12))
          }
          placeholder="AWS 계정 ID"
          className="rounded border px-3 py-2 text-sm outline-none"
          style={{
            background: "var(--color-bg)",
            color: "var(--color-text)",
            borderColor: "var(--color-border-strong)",
          }}
        />
        <input
          value={region}
          onChange={(event) => setRegion(event.target.value)}
          placeholder="ap-northeast-2"
          className="rounded border px-3 py-2 text-sm outline-none"
          style={{
            background: "var(--color-bg)",
            color: "var(--color-text)",
            borderColor: "var(--color-border-strong)",
          }}
        />
        <button
          type="submit"
          disabled={busy === "prepare" || !/^\d{12}$/.test(accountId)}
          className="rounded-md px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-accent-fg)",
          }}
        >
          연결 준비
        </button>
      </form>

      {error && (
        <div
          className="mb-4 rounded-md border px-3 py-2 text-sm"
          style={{
            borderColor: "var(--color-danger)",
            color: "var(--color-danger)",
            background: "var(--color-surface)",
          }}
        >
          {error}
        </div>
      )}
      {notice && (
        <div
          className="mb-4 rounded-md border px-3 py-2 text-sm"
          style={{
            borderColor: "var(--color-success)",
            color: "var(--color-success)",
            background: "var(--color-surface)",
          }}
        >
          {notice}
        </div>
      )}

      {loading ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          로딩 중…
        </p>
      ) : connections.length === 0 ? (
        <div
          className="rounded-md border px-4 py-10 text-center text-sm"
          style={{
            background: "var(--color-surface)",
            borderColor: "var(--color-border)",
            color: "var(--color-text-muted)",
          }}
        >
          등록된 AWS 연결이 없습니다.
        </div>
      ) : (
        <div className="space-y-3">
          {connections.map((connection) => (
            <section
              key={connection.id}
              className="rounded-md border"
              style={{
                background: "var(--color-surface)",
                borderColor: "var(--color-border)",
              }}
            >
              <div className="flex items-center justify-between gap-4 p-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h2
                      className="text-base font-semibold"
                      style={{ color: "var(--color-text)" }}
                    >
                      {connection.account_id}
                    </h2>
                    <StatusPill status={connection.binding_status} />
                    <PermissionPill mode={connection.permission_mode} />
                  </div>
                  <p
                    className="mt-1 text-xs"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    {connection.default_region}
                    {connection.last_verified_at
                      ? ` · verified ${formatDate(connection.last_verified_at)}`
                      : ""}
                  </p>
                  {connection.connected_project_groups.length > 0 && (
                    <p
                      className="mt-1 text-xs"
                      style={{ color: "var(--color-text-subtle)" }}
                    >
                      Project Groups:{" "}
                      {connection.connected_project_groups
                        .map((group) =>
                          group.is_default ? `${group.name} default` : group.name,
                        )
                        .join(", ")}
                    </p>
                  )}
                </div>
                <button
                  onClick={() =>
                    setExpandedId((current) =>
                      current === connection.id ? null : connection.id,
                    )
                  }
                  className="rounded border px-3 py-1.5 text-sm"
                  style={{
                    color: "var(--color-text)",
                    borderColor: "var(--color-border-strong)",
                  }}
                >
                  {expandedId === connection.id ? "접기" : "관리"}
                </button>
              </div>

              {expandedId === connection.id && (
                <div
                  className="space-y-4 border-t p-4"
                  style={{ borderColor: "var(--color-border)" }}
                >
                  <Field label="External ID">
                    <div className="flex gap-2">
                      <code
                        className="min-w-0 flex-1 break-all rounded px-2 py-1 text-xs"
                        style={{
                          background: "var(--color-bg-subtle)",
                          color: "var(--color-text)",
                        }}
                      >
                        {connection.external_id}
                      </code>
                      <button
                        onClick={() =>
                          copy(connection.external_id, `external:${connection.id}`)
                        }
                        className="rounded border px-2 py-1 text-xs"
                        style={{
                          color: "var(--color-text-muted)",
                          borderColor: "var(--color-border-strong)",
                        }}
                      >
                        {copied === `external:${connection.id}` ? "복사됨" : "복사"}
                      </button>
                    </div>
                  </Field>

                  <Field label="Role ARN">
                    <div className="flex gap-2">
                      <input
                        value={roleInputs[connection.id] || ""}
                        onChange={(event) =>
                          setRoleInputs((prev) => ({
                            ...prev,
                            [connection.id]: event.target.value,
                          }))
                        }
                        placeholder="arn:aws:iam::123456789012:role/IaC-role"
                        className="min-w-0 flex-1 rounded border px-3 py-2 text-sm outline-none"
                        style={{
                          background: "var(--color-bg)",
                          color: "var(--color-text)",
                          borderColor: "var(--color-border-strong)",
                        }}
                      />
                      <button
                        onClick={() => handleSaveRole(connection)}
                        disabled={busy === `role:${connection.id}`}
                        className="rounded border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
                        style={{
                          color: "var(--color-text)",
                          borderColor: "var(--color-border-strong)",
                        }}
                      >
                        {busy === `role:${connection.id}` ? "저장 중" : "저장"}
                      </button>
                      <button
                        onClick={() => handleVerify(connection)}
                        disabled={busy === `verify:${connection.id}`}
                        className="rounded px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
                        style={{
                          background: "var(--color-accent)",
                          color: "var(--color-accent-fg)",
                        }}
                      >
                        {busy === `verify:${connection.id}` ? "검증 중" : "Verify"}
                      </button>
                    </div>
                    {connection.assumed_arn && (
                      <p
                        className="mt-2 break-all text-xs"
                        style={{ color: "var(--color-text-muted)" }}
                      >
                        AssumeRole: {connection.assumed_arn}
                      </p>
                    )}
                    {connection.last_verify_error && (
                      <p
                        className="mt-2 break-all text-xs"
                        style={{ color: "var(--color-danger)" }}
                      >
                        Last verify error: {connection.last_verify_error}
                      </p>
                    )}
                  </Field>

                  {connection.cloudformation_template && (
                    <Field label="CloudFormation YAML">
                      <button
                        onClick={() =>
                          copy(
                            connection.cloudformation_template || "",
                            `template:${connection.id}`,
                          )
                        }
                        className="mb-2 rounded border px-2 py-1 text-xs"
                        style={{
                          color: "var(--color-text-muted)",
                          borderColor: "var(--color-border-strong)",
                        }}
                      >
                        {copied === `template:${connection.id}`
                          ? "템플릿 복사됨"
                          : "템플릿 복사"}
                      </button>
                      <pre className="max-h-56 overflow-auto rounded bg-[#0f172a] p-2 text-[10px] leading-relaxed text-[#e2e8f0]">
                        {connection.cloudformation_template}
                      </pre>
                    </Field>
                  )}
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </main>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        className="mb-1 text-xs font-medium"
        style={{ color: "var(--color-text-muted)" }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "verified"
      ? "var(--color-success)"
      : status === "verify_failed"
        ? "var(--color-danger)"
        : "var(--color-text-muted)";
  return (
    <span
      className="rounded px-2 py-0.5 text-[11px] font-medium"
      style={{
        color: tone,
        background: "var(--color-bg-subtle)",
      }}
    >
      {statusLabel(status)}
    </span>
  );
}

function PermissionPill({ mode }: { mode: string }) {
  return (
    <span
      className="rounded px-2 py-0.5 text-[11px] font-medium"
      style={{
        color: "var(--color-info)",
        background: "var(--color-bg-subtle)",
      }}
    >
      {permissionLabel(mode)}
    </span>
  );
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending_role: "Role 대기",
    role_saved: "Role 저장됨",
    verified: "검증 완료",
    verify_failed: "검증 실패",
    verify_unavailable: "검증 불가",
  };
  return labels[status] || status;
}

function permissionLabel(mode: string): string {
  const labels: Record<string, string> = {
    read_only: "Read-only",
    plan_ready: "Plan-ready",
    apply_enabled: "Apply-enabled",
    destroy_enabled: "Destroy-enabled",
  };
  return labels[mode] || mode;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function asMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "요청에 실패했습니다.";
}
