"use client";

import { useEffect, useState } from "react";

import type { DeploymentProgressEvent, TofuPlanResult } from "@/lib/api";

interface TofuPlanPanelProps {
  result: TofuPlanResult | null;
  mode?: "plan" | "apply" | "destroy" | null;
  status?: string | null;
  progressEvents?: DeploymentProgressEvent[];
  deploymentId?: string | null;
  assumedArn?: string | null;
  onClose: () => void;
  onApply?: () => void;
  canApply?: boolean;
  applying?: boolean;
  embedded?: boolean;
}

export function TofuPlanPanel({
  result,
  mode,
  status,
  progressEvents = [],
  deploymentId,
  assumedArn,
  onClose,
  onApply,
  canApply = false,
  applying = false,
  embedded = false,
}: TofuPlanPanelProps) {
  const planText =
    result?.plan_text ||
    result?.steps
      .map((step) => [step.step, step.stdout, step.stderr].filter(Boolean).join("\n"))
      .join("\n\n") ||
    "";
  const isPending = !result;
  const displayStatus = status || result?.deployment_status || null;
  const isDestroyMode = mode === "destroy";
  const [cliOpen, setCliOpen] = useState(false);
  const hasCliOutput = planText.trim().length > 0;
  const showApplyButton = Boolean(
    onApply &&
      (canApply ||
        applying ||
        displayStatus === "success" ||
        displayStatus === "approved"),
  );

  useEffect(() => {
    setCliOpen(false);
  }, [deploymentId]);

  return (
    <aside
      className={
        embedded
          ? "flex h-full min-h-0 flex-col overflow-hidden bg-[var(--color-surface)]"
          : "w-[520px] shrink-0 overflow-y-auto border-l border-[var(--color-border)] bg-[var(--color-surface)]"
      }
    >
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-text)]">
            {isDestroyMode ? "OpenTofu Destroy Plan" : "OpenTofu Plan"}
          </h3>
          <div
            className={
              isPending
                ? "mt-0.5 text-xs text-[var(--color-accent)]"
                : result.ok
                ? "mt-0.5 text-xs text-[var(--color-success)]"
                : "mt-0.5 text-xs text-[var(--color-danger)]"
            }
          >
            {isPending
              ? displayStatus === "planning"
                ? isDestroyMode
                  ? "Destroy Plan 실행중..."
                  : "Plan 실행중..."
                : isDestroyMode
                  ? "Destroy Plan 대기중..."
                  : "Plan 대기중..."
              : result.ok
                ? isDestroyMode
                  ? "Destroy Plan 성공"
                  : "Plan 성공"
                : result.error || (isDestroyMode ? "Destroy Plan 실패" : "Plan 실패")}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {showApplyButton && (
            <button
              onClick={onApply}
              disabled={!canApply || applying}
              className={
                !canApply || applying
                  ? "cursor-not-allowed rounded-md bg-[var(--color-surface)] px-3 py-1.5 text-xs text-[var(--color-text-subtle)]"
                  : "rounded-md bg-[var(--color-accent)] px-3 py-1.5 text-xs font-medium text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
              }
            >
              {applying ? "Applying" : displayStatus === "approved" ? "Apply" : "Approve & Apply"}
            </button>
          )}
          <button
            onClick={onClose}
            aria-label="닫기"
            className="rounded p-1 text-base leading-none text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="min-h-0 overflow-y-auto border-b border-[var(--color-border)] px-4 py-3">
        {(deploymentId || result?.deployment_id || assumedArn || result?.assumed_arn) && (
          <div className="mb-3 space-y-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2 text-[10px] text-[var(--color-text-muted)]">
            {(deploymentId || result?.deployment_id) && (
              <div>
                Deployment:{" "}
                <code className="text-[var(--color-text)]">
                  {deploymentId || result?.deployment_id}
                </code>
              </div>
            )}
            {(assumedArn || result?.assumed_arn) && (
              <div className="break-all">
                AssumeRole:{" "}
                <code className="text-[var(--color-text)]">
                  {assumedArn || result?.assumed_arn}
                </code>
              </div>
            )}
            {displayStatus && (
              <div>
                Status: <code className="text-[var(--color-text)]">{displayStatus}</code>
              </div>
            )}
          </div>
        )}
        <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          진행 상태
        </div>
        <ProgressTimeline events={progressEvents} isPending={isPending} />
        {isDestroyMode && (
          <div className="mb-3 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 px-3 py-2 text-xs leading-relaxed text-[var(--color-text)]">
            Destroy Plan입니다. CLI 결과에서 삭제 대상 리소스만 포함되는지 확인한 뒤 실행하세요.
          </div>
        )}
        {result?.apply_readiness_note && (
          <div className="mb-3 rounded-md border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-3 py-2 text-xs leading-relaxed text-[var(--color-text)]">
            {result.apply_readiness_note}
          </div>
        )}
        {result?.validation_issues && result.validation_issues.length > 0 && (
          <div className="mb-3 space-y-2 rounded-md border border-[var(--color-danger)]/40 bg-[var(--color-danger)]/5 p-3">
            <div className="text-xs font-semibold text-[var(--color-danger)]">
              수정이 필요한 컴포넌트
            </div>
            {result.validation_issues.map((issue, idx) => (
              <div
                key={`${issue.node_id || issue.display_name || idx}-${issue.field || idx}`}
                className="rounded border border-[var(--color-danger)]/20 bg-[var(--color-surface)] px-2 py-1.5 text-xs leading-relaxed text-[var(--color-text)]"
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold">
                    {issue.display_name || issue.node_id || "컴포넌트"}
                  </span>
                  {issue.field && (
                    <code className="rounded bg-[var(--color-danger)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-danger)]">
                      {issue.field}
                    </code>
                  )}
                </div>
                <div className="mt-1 text-[var(--color-text-muted)]">
                  {issue.message}
                </div>
                {issue.suggested_action && (
                  <div className="mt-0.5 text-[var(--color-text)]">
                    {issue.suggested_action}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        <div className="space-y-2">
          {result?.steps && result.steps.length > 0 && (
            <div className="pt-1 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              실행 결과
            </div>
          )}
          {result?.steps.map((step) => (
            <div
              key={step.step}
              className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <code className="text-xs text-[var(--color-text)]">
                  {step.step}
                </code>
                <span
                  className={
                    step.exit_code === 0
                      ? "rounded bg-[var(--color-success)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-success)]"
                      : "rounded bg-[var(--color-danger)]/10 px-1.5 py-0.5 text-[10px] text-[var(--color-danger)]"
                  }
                >
                  exit {step.exit_code} · {step.duration_sec}s
                </span>
              </div>
              {step.stderr && (
                <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-[#1f2937] p-2 text-[10px] leading-relaxed text-[#fecaca]">
                  {step.stderr}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="shrink-0 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
        <button
          type="button"
          onClick={() => setCliOpen((open) => !open)}
          className="flex h-10 w-full items-center justify-between px-4 text-left text-xs font-semibold text-[var(--color-text)] hover:bg-[var(--color-bg-subtle)]"
        >
          <span>CLI 결과</span>
          <span className="text-[var(--color-text-muted)]">
            {cliOpen ? "접기" : hasCliOutput ? "열기" : "대기 중"}
          </span>
        </button>
        {cliOpen && (
          <pre className="m-0 max-h-64 overflow-auto whitespace-pre-wrap bg-[#0f172a] p-3 font-mono text-xs leading-relaxed text-[#e2e8f0]">
            {planText || "아직 표시할 CLI 결과가 없습니다."}
          </pre>
        )}
      </div>
    </aside>
  );
}

function ProgressTimeline({
  events,
  isPending,
}: {
  events: DeploymentProgressEvent[];
  isPending: boolean;
}) {
  const visibleEvents = compactProgressEvents(events);

  if (visibleEvents.length === 0) {
    return (
      <div className="mb-3 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2 text-xs text-[var(--color-text-muted)]">
        {isPending
          ? "Plan 큐 등록을 기다리는 중입니다."
          : "기록된 진행 이벤트가 없습니다."}
      </div>
    );
  }

  return (
    <div className="mb-3 space-y-2 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2">
      {visibleEvents.map((event, index) => (
        <div
          key={`${event.step}-${event.timestamp || index}`}
          className="grid grid-cols-[14px_minmax(0,1fr)] gap-2 text-xs"
        >
          <span
            className={[
              "mt-1 h-2 w-2 rounded-full",
              event.status === "running"
                ? "bg-[var(--color-accent)]"
                : event.status === "success"
                  ? "bg-[var(--color-success)]"
                  : event.status === "warning"
                    ? "bg-[var(--color-warning)]"
                    : event.status === "failed"
                      ? "bg-[var(--color-danger)]"
                      : "bg-[var(--color-text-muted)]",
            ].join(" ")}
          />
          <div className="min-w-0">
            <div className="flex min-w-0 items-center justify-between gap-2">
              <span className="truncate font-medium text-[var(--color-text)]">
                {event.label || event.step}
              </span>
              <span className="shrink-0 rounded bg-[var(--color-surface)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-muted)]">
                {statusLabel(event.status)}
              </span>
            </div>
            {event.message && (
              <div className="mt-0.5 break-all text-[var(--color-text-muted)]">
                {event.message}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function compactProgressEvents(events: DeploymentProgressEvent[]) {
  const order: string[] = [];
  const byStep = new Map<string, DeploymentProgressEvent>();

  for (const event of events) {
    const key = event.step || event.label;
    if (!byStep.has(key)) order.push(key);
    byStep.set(key, event);
  }

  return order
    .map((key) => byStep.get(key))
    .filter((event): event is DeploymentProgressEvent => Boolean(event));
}

function statusLabel(status: string) {
  if (status === "running") return "진행 중";
  if (status === "success") return "완료";
  if (status === "warning") return "전환";
  if (status === "failed") return "실패";
  return status;
}
