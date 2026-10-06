"use client";

import { useMemo, useState } from "react";
import {
  bootstrapAwsAccount,
  saveAwsRoleArn,
  verifyAwsRole,
  type AwsAccount,
  type AwsBootstrapResult,
  type AwsVerifyResult,
} from "@/lib/api";

interface AwsAccountPanelProps {
  canvasId: string;
  awsAccount?: AwsAccount | null;
  onClose: () => void;
  onUpdated: (awsAccount: AwsAccount) => void;
}

export function AwsAccountPanel({
  canvasId,
  awsAccount,
  onClose,
  onUpdated,
}: AwsAccountPanelProps) {
  const account = (awsAccount || {}) as AwsAccount & {
    external_id?: string;
    role_arn?: string;
    binding_status?: string;
  };
  const [accountId, setAccountId] = useState(account.account_id || "");
  const [region, setRegion] = useState(account.default_region || "ap-northeast-2");
  const [roleArn, setRoleArn] = useState(account.role_arn || "");
  const [bootstrap, setBootstrap] = useState<AwsBootstrapResult | null>(null);
  const [verifyResult, setVerifyResult] = useState<AwsVerifyResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const externalId = bootstrap?.external_id || account.external_id || "";
  const status = verifyResult?.status || account.binding_status || "not_started";
  const canBootstrap = /^\d{12}$/.test(accountId);
  const canSaveRole = roleArn.trim().length > 0;

  const templateText = bootstrap?.cloudformation_template || "";
  const statusLabel = useMemo(() => {
    const labels: Record<string, string> = {
      not_started: "미시작",
      pending_role: "Role 생성 대기",
      role_saved: "Role ARN 저장됨",
      verify_failed: "검증 실패",
      verified: "검증 완료",
      verify_unavailable: "검증 불가",
    };
    return labels[status] || status;
  }, [status]);

  async function copy(text: string, key: string) {
    await navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 1500);
  }

  async function handleBootstrap() {
    setBusy(true);
    setError(null);
    try {
      const result = await bootstrapAwsAccount(canvasId, {
        account_id: accountId,
        region,
      });
      setBootstrap(result);
      setRoleArn(result.role_arn || roleArn);
      onUpdated({
        ...(awsAccount || { default_region: region, default_tags: {} }),
        account_id: result.account_id,
        default_region: result.region,
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveRole() {
    setBusy(true);
    setError(null);
    try {
      const updated = await saveAwsRoleArn(canvasId, roleArn);
      onUpdated(updated);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify() {
    setBusy(true);
    setError(null);
    try {
      const result = await verifyAwsRole(canvasId);
      setVerifyResult(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="w-full shrink-0 overflow-y-auto bg-[var(--color-surface)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          AWS 계정 연결
        </h3>
        <button
          onClick={onClose}
          aria-label="닫기"
          className="rounded p-1 text-base leading-none text-[var(--color-text-subtle)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)]"
        >
          ✕
        </button>
      </div>

      <div className="mb-4 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
        상태: <strong className="text-[var(--color-text)]">{statusLabel}</strong>
      </div>

      {error && (
        <div className="mb-3 rounded-md border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 px-3 py-2 text-xs text-[var(--color-danger)]">
          {error}
        </div>
      )}

      <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
        AWS 계정 ID
      </label>
      <input
        value={accountId}
        onChange={(e) => setAccountId(e.target.value.replace(/\D/g, "").slice(0, 12))}
        placeholder="123456789012"
        className="mb-3 w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
      />

      <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
        기본 리전
      </label>
      <input
        value={region}
        onChange={(e) => setRegion(e.target.value)}
        placeholder="ap-northeast-2"
        className="mb-3 w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
      />

      <button
        onClick={handleBootstrap}
        disabled={busy || !canBootstrap}
        className={
          busy || !canBootstrap
            ? "mb-4 w-full cursor-not-allowed rounded-md bg-[var(--color-bg-subtle)] px-3 py-2 text-sm text-[var(--color-text-subtle)]"
            : "mb-4 w-full rounded-md bg-[var(--color-accent)] px-3 py-2 text-sm font-medium text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
        }
      >
        AWS 연결 준비 / 재사용
      </button>

      {externalId && (
        <div className="mb-4 rounded-md border border-[var(--color-border)] px-3 py-2">
          <div className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">
            External ID
          </div>
          <code className="block break-all rounded bg-[var(--color-bg-subtle)] px-2 py-1 text-xs text-[var(--color-text)]">
            {externalId}
          </code>
          <button
            onClick={() => copy(externalId, "external")}
            className="mt-2 rounded border border-[var(--color-border-strong)] px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            {copied === "external" ? "복사됨" : "복사"}
          </button>
        </div>
      )}

      {bootstrap?.cloudformation_quick_create_url && (
        <a
          href={bootstrap.cloudformation_quick_create_url}
          target="_blank"
          rel="noreferrer"
          className="mb-3 block rounded-md border border-[var(--color-accent)] px-3 py-2 text-center text-sm font-medium text-[var(--color-accent)] hover:bg-[var(--color-bg-subtle)]"
        >
          AWS Console 에서 Stack 생성
        </a>
      )}

      {templateText && (
        <div className="mb-4">
          <button
            onClick={() => copy(templateText, "template")}
            className="mb-2 rounded border border-[var(--color-border-strong)] px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            {copied === "template" ? "템플릿 복사됨" : "CloudFormation YAML 복사"}
          </button>
          <pre className="max-h-48 overflow-auto rounded bg-[#0f172a] p-2 text-[10px] leading-relaxed text-[#e2e8f0]">
            {templateText}
          </pre>
        </div>
      )}

      <label className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
        Role ARN
      </label>
      <input
        value={roleArn}
        onChange={(e) => setRoleArn(e.target.value)}
        placeholder="arn:aws:iam::123456789012:role/EolgaeDeployRole"
        className="mb-2 w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
      />
      <div className="mb-4 flex gap-2">
        <button
          onClick={handleSaveRole}
          disabled={busy || !canSaveRole}
          className="flex-1 rounded border border-[var(--color-border-strong)] px-3 py-1.5 text-sm text-[var(--color-text)] disabled:cursor-not-allowed disabled:text-[var(--color-text-subtle)]"
        >
          Role 저장
        </button>
        <button
          onClick={handleVerify}
          disabled={busy || !roleArn || !externalId}
          className="flex-1 rounded bg-[var(--color-accent)] px-3 py-1.5 text-sm text-[var(--color-accent-fg)] disabled:cursor-not-allowed disabled:bg-[var(--color-bg-subtle)] disabled:text-[var(--color-text-subtle)]"
        >
          검증
        </button>
      </div>

      {verifyResult && (
        <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
          <div className={verifyResult.ok ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {verifyResult.message}
          </div>
          {verifyResult.assumed_arn && (
            <code className="mt-1 block break-all text-[var(--color-text-subtle)]">
              {verifyResult.assumed_arn}
            </code>
          )}
        </div>
      )}
    </aside>
  );
}
