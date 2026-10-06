import { NodeDensityToggle } from "@/components/NodeDensityToggle";
import { ThemeToggle } from "@/components/ThemeToggle";

export function InspectorControls({
  showAwsAction = true,
  awsVerified,
  feedbackLoading,
  hasFeedback,
  isStale,
  autoReflect,
  hiddenCount,
  showHidden,
  containedNodeCount,
  showContainmentBadges,
  onAwsToggle,
  onKubernetesToggle,
  onFeedbackOpen,
  onIacOpen,
  onToggleShowHidden,
  onToggleContainmentBadges,
}: {
  showAwsAction?: boolean;
  awsVerified: boolean;
  feedbackLoading: boolean;
  hasFeedback: boolean;
  isStale: boolean;
  autoReflect: boolean;
  hiddenCount: number;
  showHidden: boolean;
  containedNodeCount: number;
  showContainmentBadges: boolean;
  onAwsToggle: () => void;
  onKubernetesToggle: () => void;
  onFeedbackOpen: () => void;
  onIacOpen: () => void;
  onToggleShowHidden: () => void;
  onToggleContainmentBadges: () => void;
}) {
  return (
    <div className="bg-[var(--color-bg-subtle)] p-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
        Actions
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {showAwsAction && (
          <button
            onClick={onAwsToggle}
            className={
              awsVerified
                ? "min-w-0 rounded-md border border-[var(--color-success)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-success)]"
                : "min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            }
          >
            AWS
          </button>
        )}
        <button
          onClick={onKubernetesToggle}
          className="min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        >
          K8s
        </button>
        <button
          onClick={onFeedbackOpen}
          className="min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        >
          <span className="inline-block max-w-full truncate align-bottom">
            AI피드백
          </span>
          {feedbackLoading && (
            <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-accent)] eolgae-pulse align-middle" />
          )}
          {!feedbackLoading && hasFeedback && isStale && autoReflect && (
            <span className="ml-1.5 text-[var(--color-warning)]">!</span>
          )}
        </button>
        <button
          onClick={onIacOpen}
          className="min-w-0 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        >
          IaC
        </button>
      </div>

      <div className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
        View
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {hiddenCount > 0 && (
          <button
            onClick={onToggleShowHidden}
            className={
              showHidden
                ? "rounded-md border border-[var(--color-accent)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-accent)]"
                : "rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            }
          >
            Hidden {hiddenCount}
          </button>
        )}
        {containedNodeCount > 0 && (
          <button
            onClick={onToggleContainmentBadges}
            className={
              showContainmentBadges
                ? "rounded-md border border-[var(--color-accent)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs font-medium text-[var(--color-accent)]"
                : "rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-xs text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            }
          >
            Groups
          </button>
        )}
        <NodeDensityToggle />
        <ThemeToggle />
      </div>
    </div>
  );
}
