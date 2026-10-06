import { type KubernetesValidationResult } from "@/lib/api";

export function KubernetesValidationSummary({
  result,
}: {
  result: KubernetesValidationResult;
}) {
  return (
    <div className="shrink-0 border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs font-semibold text-[var(--color-text)]">
          Validation {result.ok ? "passed" : "needs attention"}
        </div>
        <div className="flex gap-1 text-[10px]">
          <span className="rounded bg-[var(--color-surface)] px-1.5 py-0.5 text-[var(--color-text-muted)]">
            resources {result.summary.resources}
          </span>
          <span className="rounded bg-[var(--color-surface)] px-1.5 py-0.5 text-[var(--color-danger)]">
            errors {result.summary.errors}
          </span>
          <span className="rounded bg-[var(--color-surface)] px-1.5 py-0.5 text-[var(--color-warning)]">
            warnings {result.summary.warnings}
          </span>
        </div>
      </div>
      {result.issues.length > 0 && (
        <div className="mt-2 flex flex-col gap-1">
          {result.issues.slice(0, 3).map((issue) => (
            <div
              key={`${issue.code}-${issue.node_id || "canvas"}`}
              className="truncate text-xs text-[var(--color-text-muted)]"
            >
              <span
                className={
                  issue.severity === "error"
                    ? "font-semibold text-[var(--color-danger)]"
                    : "font-semibold text-[var(--color-warning)]"
                }
              >
                {issue.severity}
              </span>{" "}
              {issue.message}
            </div>
          ))}
        </div>
      )}
      {result.dry_run && (
        <div className="mt-2 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-[11px] text-[var(--color-text-muted)]">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold text-[var(--color-text)]">Dry-run</span>
            <span className={dryRunModeClass(result.dry_run.mode)}>
              {dryRunModeLabel(result.dry_run.mode)}
            </span>
            {result.dry_run.namespace && (
              <span className="rounded bg-[var(--color-bg-subtle)] px-1.5 py-0.5 text-[var(--color-text-subtle)]">
                ns/{result.dry_run.namespace}
              </span>
            )}
          </div>
          <div className="mt-1 truncate">{result.dry_run.message}</div>
          {result.dry_run.blocked_by && (
            <div className="mt-1 truncate text-[10px] text-[var(--color-text-subtle)]">
              blocked by {result.dry_run.blocked_by.replaceAll("_", " ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function dryRunModeLabel(mode: string): string {
  if (mode === "credentials_resolved") return "credentials resolved";
  if (mode === "credentials_pending") return "credentials pending";
  if (mode === "local_validation_failed") return "local validation failed";
  if (mode === "not_configured") return "target missing";
  return mode.replaceAll("_", " ");
}

function dryRunModeClass(mode: string): string {
  if (mode === "credentials_resolved") {
    return "rounded bg-[var(--color-success)]/10 px-1.5 py-0.5 text-[var(--color-success)]";
  }
  if (mode === "credentials_pending" || mode === "not_configured") {
    return "rounded bg-[var(--color-warning)]/10 px-1.5 py-0.5 text-[var(--color-warning)]";
  }
  if (mode === "local_validation_failed") {
    return "rounded bg-[var(--color-danger)]/10 px-1.5 py-0.5 text-[var(--color-danger)]";
  }
  return "rounded bg-[var(--color-bg-subtle)] px-1.5 py-0.5 text-[var(--color-text-subtle)]";
}
