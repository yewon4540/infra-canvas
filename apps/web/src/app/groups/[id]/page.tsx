"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiError,
  addCanvasToGroup,
  deleteGroup,
  getGroup,
  listCanvases,
  listGroupCanvases,
  removeCanvasFromGroup,
  updateGroup,
  type ApiCanvasGroup,
  type Canvas,
  type CanvasInGroup,
} from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";
import { ConfirmModal } from "@/components/ConfirmModal";

export default function GroupDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [group, setGroup] = useState<ApiCanvasGroup | null>(null);
  const [canvases, setCanvases] = useState<CanvasInGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [allCanvases, setAllCanvases] = useState<Canvas[] | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");

  useEffect(() => {
    Promise.all([getGroup(id), listGroupCanvases(id)])
      .then(([g, cs]) => {
        setGroup(g);
        setNameDraft(g.name);
        setCanvases(cs);
      })
      .catch((e) => setError(asMessage(e)))
      .finally(() => setLoading(false));
  }, [id]);

  async function openAddCanvas() {
    setAddOpen(true);
    if (allCanvases === null) {
      try {
        const all = await listCanvases();
        setAllCanvases(all);
      } catch (e) {
        setError(asMessage(e));
      }
    }
  }

  async function handleAdd(canvasId: string) {
    setError(null);
    try {
      const added = await addCanvasToGroup(id, canvasId);
      setCanvases((prev) => [added, ...prev.filter((c) => c.id !== added.id)]);
      setAddOpen(false);
    } catch (e) {
      setError(asMessage(e));
    }
  }

  async function handleRemove(canvasId: string) {
    setError(null);
    try {
      await removeCanvasFromGroup(id, canvasId);
      setCanvases((prev) => prev.filter((c) => c.id !== canvasId));
    } catch (e) {
      setError(asMessage(e));
    }
  }

  async function handleRenameSave() {
    if (!group) return;
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === group.name) {
      setEditingName(false);
      setNameDraft(group.name);
      return;
    }
    try {
      const updated = await updateGroup(id, { name: trimmed });
      setGroup(updated);
      setNameDraft(updated.name);
      setEditingName(false);
    } catch (e) {
      setError(asMessage(e));
    }
  }

  async function handleDeleteConfirmed() {
    setPendingDelete(false);
    try {
      await deleteGroup(id);
      router.push("/groups");
    } catch (e) {
      setError(asMessage(e));
    }
  }

  const inGroupIds = new Set(canvases.map((c) => c.id));
  const addableCanvases =
    allCanvases?.filter((c) => !inGroupIds.has(c.id)) ?? [];

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <Link
            href="/groups"
            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
            style={{
              color: "var(--color-text)",
              borderColor: "var(--color-border)",
            }}
          >
            <span aria-hidden="true">←</span>
            Project Groups
          </Link>
          {editingName ? (
            <div className="mt-1 flex items-center gap-2">
              <input
                autoFocus
                value={nameDraft}
                onChange={(e) => setNameDraft(e.target.value)}
                onBlur={handleRenameSave}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRenameSave();
                  if (e.key === "Escape") {
                    setEditingName(false);
                    setNameDraft(group?.name ?? "");
                  }
                }}
                maxLength={200}
                className="rounded border px-2 py-1 text-2xl font-bold outline-none"
                style={{
                  background: "var(--color-surface)",
                  color: "var(--color-text)",
                  borderColor: "var(--color-border-strong)",
                }}
              />
            </div>
          ) : (
            <h1
              className="mt-1 cursor-text text-2xl font-bold tracking-tight"
              style={{ color: "var(--color-text)" }}
              onDoubleClick={() => setEditingName(true)}
              title="더블클릭으로 이름 변경"
            >
              {group?.name ?? "…"}
            </h1>
          )}
          {group?.description && (
            <p
              className="mt-1 text-sm"
              style={{ color: "var(--color-text-muted)" }}
            >
              {group.description}
            </p>
          )}
          {group && (
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--color-text-muted)]">
              <span className="rounded bg-[var(--color-bg-subtle)] px-2 py-1">
                {group.status}
              </span>
              {group.default_environment && (
                <span className="rounded bg-[var(--color-bg-subtle)] px-2 py-1">
                  env {group.default_environment.slug}
                </span>
              )}
              {group.default_aws_connection && (
                <span className="rounded bg-[var(--color-bg-subtle)] px-2 py-1">
                  aws {group.default_aws_connection.account_id}
                </span>
              )}
              <span className="rounded bg-[var(--color-bg-subtle)] px-2 py-1">
                {group.connected_aws_connections.length} AWS connections
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <UserMenu />
          <ThemeToggle />
        </div>
      </div>

      <div className="mb-5 flex items-center gap-2">
        <button
          onClick={openAddCanvas}
          className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition-colors hover:bg-[var(--color-accent-hover)]"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-accent-fg)",
          }}
        >
          + Canvas 추가
        </button>
        <button
          onClick={() => setPendingDelete(true)}
          className="cursor-pointer rounded-md border px-3 py-2 text-sm font-medium transition-colors hover:bg-[var(--color-danger)]/10"
          style={{
            color: "var(--color-danger)",
            borderColor: "var(--color-border)",
          }}
        >
          Project Group 삭제
        </button>
      </div>

      {error && (
        <p
          className="mb-4 text-sm"
          style={{ color: "var(--color-danger)" }}
        >
          오류: {error}
        </p>
      )}

      {loading ? (
        <p style={{ color: "var(--color-text-muted)" }}>불러오는 중…</p>
      ) : canvases.length === 0 ? (
        <div
          className="rounded-md border border-dashed p-10 text-center text-sm"
          style={{
            borderColor: "var(--color-border)",
            color: "var(--color-text-muted)",
          }}
        >
          이 Project Group에 담긴 Canvas가 없습니다.
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {canvases.map((c) => (
            <li
              key={c.id}
              className="group relative rounded-md border p-4"
              style={{
                background: "var(--color-surface)",
                borderColor: "var(--color-border)",
              }}
            >
              <Link href={`/canvas/${c.id}`} className="block">
                <h3
                  className="text-base font-semibold"
                  style={{ color: "var(--color-text)" }}
                >
                  {c.name}
                </h3>
                {c.description && (
                  <p
                    className="mt-2 text-sm line-clamp-2"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    {c.description}
                  </p>
                )}
                <p
                  className="mt-3 text-xs"
                  style={{ color: "var(--color-text-subtle)" }}
                >
                  {STATE_LABEL[c.state]} · {new Date(c.updated_at).toLocaleDateString()}
                </p>
              </Link>
              <button
                onClick={() => handleRemove(c.id)}
                className="absolute right-3 top-3 hidden cursor-pointer rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-danger)] group-hover:block"
                style={{
                  color: "var(--color-text-muted)",
                  borderColor: "var(--color-border)",
                }}
                aria-label="Project Group에서 빼기"
              >
                빼기
              </button>
            </li>
          ))}
        </ul>
      )}

      {addOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setAddOpen(false)}
        >
          <div
            className="max-h-[80vh] w-full max-w-md overflow-hidden rounded-lg border shadow-lg"
            style={{
              background: "var(--color-surface)",
              borderColor: "var(--color-border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="border-b px-4 py-3 text-sm font-semibold"
              style={{
                borderColor: "var(--color-border)",
                color: "var(--color-text)",
              }}
            >
              캔버스 담기
            </div>
            <div className="max-h-96 overflow-y-auto">
              {allCanvases === null ? (
                <p
                  className="px-4 py-6 text-center text-sm"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  불러오는 중…
                </p>
              ) : addableCanvases.length === 0 ? (
                <p
                  className="px-4 py-6 text-center text-sm"
                  style={{ color: "var(--color-text-muted)" }}
                >
                  담을 수 있는 캔버스가 없습니다.
                </p>
              ) : (
                <ul>
                  {addableCanvases.map((c) => (
                    <li key={c.id}>
                      <button
                        onClick={() => handleAdd(c.id)}
                        className="block w-full cursor-pointer px-4 py-3 text-left text-sm transition-colors hover:bg-[var(--color-bg-subtle)]"
                        style={{ color: "var(--color-text)" }}
                      >
                        <div className="font-medium">{c.name}</div>
                        <div
                          className="text-xs"
                          style={{ color: "var(--color-text-subtle)" }}
                        >
                          {new Date(c.updated_at).toLocaleDateString()}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div
              className="flex justify-end border-t px-4 py-2"
              style={{ borderColor: "var(--color-border)" }}
            >
              <button
                onClick={() => setAddOpen(false)}
                className="cursor-pointer rounded px-3 py-1.5 text-sm hover:bg-[var(--color-bg-subtle)]"
                style={{ color: "var(--color-text-muted)" }}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}

      {pendingDelete && (
        <ConfirmModal
          title="Project Group 삭제"
          message={`'${group?.name ?? ""}' Project Group을 휴지통으로 이동할까요? 안의 Canvas는 삭제되지 않습니다.`}
          confirmLabel="삭제"
          cancelLabel="취소"
          danger
          onConfirm={handleDeleteConfirmed}
          onCancel={() => setPendingDelete(false)}
        />
      )}
    </main>
  );
}

const STATE_LABEL: Record<Canvas["state"], string> = {
  design: "Design",
  deploy: "Apply",
  running: "Apply",
  applied: "Apply",
  destroyed: "Destroy",
};

function asMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "알 수 없는 오류";
}
