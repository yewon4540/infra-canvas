import type { CanvasState } from "@/lib/api";

type CanvasToolbarProps = {
  canvasName: string;
  canvasState: CanvasState;
  saveStatus: "saved" | "dirty" | "saving" | "error";
  autoSaveEnabled: boolean;
  editingName: boolean;
  nameInput: string;
  onSave: () => void;
  onAutoSaveChange: (enabled: boolean) => void;
  onNameInputChange: (value: string) => void;
  onNameEditStart: () => void;
  onNameSave: () => void;
  onNameEditCancel: () => void;
};

export function CanvasToolbar({
  canvasName,
  canvasState,
  saveStatus,
  autoSaveEnabled,
  editingName,
  nameInput,
  onSave,
  onAutoSaveChange,
  onNameInputChange,
  onNameEditStart,
  onNameSave,
  onNameEditCancel,
}: CanvasToolbarProps) {
  const canvasStateLabel = getCanvasStateLabel(canvasState);
  const canvasStateTone = getCanvasStateTone(canvasState);
  const statusLabel =
    saveStatus === "saving"
      ? "저장중"
      : saveStatus === "dirty"
        ? "변경됨"
        : saveStatus === "error"
          ? "저장 실패"
          : "저장됨";

  return (
    <div className="absolute left-3 top-3 z-10 flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 shadow-[var(--shadow-md)]">
      {editingName ? (
        <input
          type="text"
          value={nameInput}
          autoFocus
          onChange={(e) => onNameInputChange(e.target.value)}
          onBlur={onNameSave}
          onFocus={(e) => e.target.select()}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onNameSave();
            } else if (e.key === "Escape") {
              onNameEditCancel();
            }
          }}
          className="min-w-[140px] rounded border border-[var(--color-accent)] bg-[var(--color-surface)] px-1.5 py-0.5 text-sm font-semibold text-[var(--color-text)] outline-none focus:ring-2 focus:ring-[var(--color-accent)]/30"
        />
      ) : (
        <strong
          onClick={onNameEditStart}
          title="클릭하여 이름 변경"
          className="cursor-text rounded px-1.5 py-0.5 text-sm text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-subtle)]"
        >
          {canvasName}
        </strong>
      )}
      <span className="min-w-[4rem] text-xs text-[var(--color-text-subtle)]">
        {saveStatus === "saving" ? (
          <span className="flex items-center gap-1.5">
            <span className="eolgae-pulse inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
            {statusLabel}
          </span>
        ) : (
          statusLabel
        )}
      </span>
      <span
        className={[
          "rounded px-2 py-0.5 text-xs font-semibold",
          canvasStateTone === "success"
            ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
            : canvasStateTone === "danger"
              ? "bg-[var(--color-danger)]/10 text-[var(--color-danger)]"
              : "bg-[var(--color-bg-subtle)] text-[var(--color-text-muted)]",
        ].join(" ")}
        title={`Canvas state: ${canvasState}`}
      >
        {canvasStateLabel}
      </span>
      <button
        type="button"
        onClick={onSave}
        disabled={saveStatus === "saving" || saveStatus === "saved"}
        className="rounded border border-[var(--color-border)] px-2 py-1 text-xs font-medium text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-subtle)] disabled:cursor-not-allowed disabled:opacity-45"
        title="저장 (Ctrl/Cmd+S)"
      >
        저장
      </button>
      <label className="flex items-center gap-1.5 text-xs text-[var(--color-text-subtle)]">
        <input
          type="checkbox"
          checked={autoSaveEnabled}
          onChange={(e) => onAutoSaveChange(e.target.checked)}
          className="h-3.5 w-3.5 accent-[var(--color-accent)]"
        />
        자동저장
      </label>
    </div>
  );
}

function getCanvasStateLabel(state: CanvasState) {
  if (state === "applied" || state === "running" || state === "deploy") {
    return "Apply";
  }
  if (state === "destroyed") return "Destroy";
  return "Design";
}

function getCanvasStateTone(state: CanvasState) {
  if (state === "applied" || state === "running" || state === "deploy") {
    return "success";
  }
  if (state === "destroyed") return "danger";
  return "neutral";
}
