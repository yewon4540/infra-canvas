"use client";

import { useEffect } from "react";

interface ConfirmModalProps {
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmModal({
  title,
  message,
  confirmLabel = "확인",
  cancelLabel = "취소",
  danger,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
      else if (e.key === "Enter") onConfirm();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, onConfirm]);

  return (
    <div
      onClick={onCancel}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px]"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        className="w-[min(90vw,440px)] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-xl"
      >
        <h3 className="mb-2 text-base font-semibold text-[var(--color-text)]">
          {title}
        </h3>
        <div className="mb-5 text-sm leading-relaxed text-[var(--color-text-muted)]">
          {message}
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-subtle)]"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            autoFocus
            className={
              danger
                ? "rounded border border-transparent bg-[var(--color-danger)] px-3 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
                : "rounded border border-transparent bg-[var(--color-accent)] px-3 py-1.5 text-sm font-medium text-[var(--color-accent-fg)] transition-opacity hover:opacity-90"
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
