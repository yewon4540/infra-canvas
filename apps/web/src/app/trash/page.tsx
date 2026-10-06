"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listTrash,
  permanentDeleteCanvas,
  restoreCanvas,
  type Canvas,
} from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ConfirmModal } from "@/components/ConfirmModal";
import { UserMenu } from "@/components/UserMenu";

export default function TrashPage() {
  const [canvases, setCanvases] = useState<Canvas[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingPurge, setPendingPurge] = useState<Canvas | null>(null);

  useEffect(() => {
    listTrash()
      .then(setCanvases)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleRestore(id: string) {
    try {
      await restoreCanvas(id);
      setCanvases((prev) => prev.filter((c) => c.id !== id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handlePurgeConfirmed() {
    if (!pendingPurge) return;
    const target = pendingPurge;
    setPendingPurge(null);
    try {
      await permanentDeleteCanvas(target.id);
      setCanvases((prev) => prev.filter((c) => c.id !== target.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link
            href="/canvas"
            className="text-sm text-[var(--color-accent)] hover:underline"
          >
            ← 캔버스 목록
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--color-text)]">
            🗑 휴지통
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            삭제된 캔버스 — 복구 또는 영구 삭제 가능
          </p>
        </div>
        <div className="flex items-center gap-2">
          <UserMenu />
          <ThemeToggle />
        </div>
      </div>

      {error && (
        <p className="mb-4 text-sm text-[var(--color-danger)]">오류: {error}</p>
      )}

      {loading ? (
        <div className="p-10 text-center text-sm text-[var(--color-text-subtle)]">
          로딩중...
        </div>
      ) : canvases.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--color-border-strong)] p-10 text-center text-sm text-[var(--color-text-muted)]">
          휴지통 비어있음.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {canvases.map((c) => (
            <li
              key={c.id}
              className="flex items-stretch overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]"
            >
              <div className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold text-[var(--color-text)]">
                    {c.name}
                  </div>
                  <div className="mt-0.5 text-xs text-[var(--color-text-subtle)]">
                    삭제됨:{" "}
                    {c.deleted_at
                      ? new Date(c.deleted_at).toLocaleString("ko-KR")
                      : "-"}
                  </div>
                </div>
              </div>
              <button
                onClick={() => handleRestore(c.id)}
                title="복구"
                className="border-l border-[var(--color-border)] bg-transparent px-3.5 text-sm text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)]"
              >
                복구
              </button>
              <button
                onClick={() => setPendingPurge(c)}
                title="영구 삭제 (복구 불가)"
                className="border-l border-[var(--color-border)] bg-transparent px-3.5 text-sm text-[var(--color-text-subtle)] transition-colors hover:bg-[var(--color-danger)]/10 hover:text-[var(--color-danger)]"
              >
                영구 삭제
              </button>
            </li>
          ))}
        </ul>
      )}

      {pendingPurge && (
        <ConfirmModal
          title="영구 삭제"
          message={
            <>
              <strong>‘{pendingPurge.name}’</strong> 을(를){" "}
              <strong>영구 삭제</strong>합니다.
              <br />
              <span className="text-[var(--color-danger)]">
                복구 불가능합니다.
              </span>
            </>
          }
          confirmLabel="영구 삭제"
          cancelLabel="취소"
          danger
          onConfirm={handlePurgeConfirmed}
          onCancel={() => setPendingPurge(null)}
        />
      )}
    </main>
  );
}
