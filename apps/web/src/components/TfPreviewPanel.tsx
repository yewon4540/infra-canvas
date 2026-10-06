"use client";

import { useState } from "react";

interface TfPreviewPanelProps {
  tf: string;
  filename: string;
  onClose: () => void;
  onDownload: () => void;
  embedded?: boolean;
  title?: string;
  downloadLabel?: string;
}

export function TfPreviewPanel({
  tf,
  filename,
  onClose,
  onDownload,
  embedded = false,
  title = "OpenTofu 미리보기",
  downloadLabel = ".tf 다운로드",
}: TfPreviewPanelProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(tf).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      },
      () => {},
    );
  }

  return (
    <div
      className={
        embedded
          ? "flex h-full min-h-0 flex-col bg-[var(--color-surface)]"
          : "absolute right-0 top-0 bottom-0 z-10 flex w-[480px] flex-col border-l border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-lg)]"
      }
    >
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-4 py-3">
        <strong className="text-sm text-[var(--color-text)]">
          {title}
        </strong>
        <button
          onClick={onClose}
          aria-label="닫기"
          className="rounded p-1 text-base leading-none text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
        >
          ✕
        </button>
      </div>
      <div className="border-b border-[var(--color-border)] px-4 py-2 text-xs text-[var(--color-text-muted)]">
        파일명:{" "}
        <code className="rounded bg-[var(--color-bg-subtle)] px-1.5 py-0.5 font-mono text-xs">
          {filename}
        </code>{" "}
        · {tf.split("\n").length} 줄
      </div>
      <pre className="m-0 flex-1 overflow-auto whitespace-pre bg-[#0f172a] p-3 font-mono text-xs leading-relaxed text-[#e2e8f0]">
        {tf}
      </pre>
      <div className="flex items-center gap-2 border-t border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-4 py-2.5">
        <button
          onClick={handleCopy}
          className={
            copied
              ? "rounded border border-[var(--color-success)] bg-[var(--color-success)] px-3 py-1.5 text-sm text-white"
              : "rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-1.5 text-sm text-[var(--color-text)] hover:bg-[var(--color-bg-subtle)]"
          }
        >
          {copied ? "복사됨" : "복사"}
        </button>
        <button
          onClick={onDownload}
          className="rounded bg-[var(--color-accent)] px-3 py-1.5 text-sm text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
        >
          {downloadLabel}
        </button>
        <button
          onClick={onClose}
          className="ml-auto rounded border border-[var(--color-border-strong)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-bg-subtle)]"
        >
          닫기
        </button>
      </div>
    </div>
  );
}
