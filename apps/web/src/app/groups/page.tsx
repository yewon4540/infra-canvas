"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiError,
  createGroup,
  deleteGroup,
  listGroups,
  type ApiCanvasGroup,
} from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";
import { ConfirmModal } from "@/components/ConfirmModal";

export default function GroupsPage() {
  const router = useRouter();
  const [groups, setGroups] = useState<ApiCanvasGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newOpen, setNewOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ApiCanvasGroup | null>(
    null,
  );

  useEffect(() => {
    listGroups()
      .then(setGroups)
      .catch((e) => setError(asMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createGroup({ name: newName.trim() });
      setGroups((prev) => [...prev, created]);
      setNewName("");
      setNewOpen(false);
      router.push(`/groups/${created.id}`);
    } catch (e) {
      setError(asMessage(e));
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteConfirmed() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    try {
      await deleteGroup(target.id);
      setGroups((prev) => prev.filter((g) => g.id !== target.id));
    } catch (e) {
      setError(asMessage(e));
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link
            href="/settings"
            className="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
            style={{
              color: "var(--color-text)",
              borderColor: "var(--color-border)",
            }}
          >
            <span aria-hidden="true">←</span>
            환경설정
          </Link>
          <h1
            className="mt-1 text-2xl font-bold tracking-tight"
            style={{ color: "var(--color-text)" }}
          >
            Project Groups
          </h1>
          <p
            className="mt-1 text-sm"
            style={{ color: "var(--color-text-muted)" }}
          >
            캔버스, AWS 연결, 운영 이력을 업무/프로젝트 단위로 분류합니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <UserMenu />
          <ThemeToggle />
        </div>
      </div>

      <div className="mb-5">
        {newOpen ? (
          <form
            onSubmit={handleCreate}
            className="flex items-center gap-2 rounded-md border p-3"
            style={{
              background: "var(--color-surface)",
              borderColor: "var(--color-border)",
            }}
          >
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            placeholder="Project Group name"
              maxLength={200}
              className="flex-1 rounded border px-3 py-1.5 text-sm outline-none"
              style={{
                background: "var(--color-bg)",
                color: "var(--color-text)",
                borderColor: "var(--color-border-strong)",
              }}
            />
            <button
              type="submit"
              disabled={creating || !newName.trim()}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-60"
              style={{
                background: "var(--color-accent)",
                color: "var(--color-accent-fg)",
              }}
            >
              {creating ? "생성 중…" : "생성"}
            </button>
            <button
              type="button"
              onClick={() => {
                setNewOpen(false);
                setNewName("");
              }}
              className="rounded-md px-3 py-1.5 text-sm"
              style={{ color: "var(--color-text-muted)" }}
            >
              취소
            </button>
          </form>
        ) : (
          <button
            onClick={() => setNewOpen(true)}
            className="cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition-colors hover:bg-[var(--color-accent-hover)]"
            style={{
              background: "var(--color-accent)",
              color: "var(--color-accent-fg)",
            }}
          >
            + 새 Project Group
          </button>
        )}
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
        <p
          className="text-sm"
          style={{ color: "var(--color-text-muted)" }}
        >
          불러오는 중…
        </p>
      ) : groups.length === 0 ? (
        <div
          className="rounded-md border border-dashed p-10 text-center text-sm"
          style={{
            borderColor: "var(--color-border)",
            color: "var(--color-text-muted)",
          }}
        >
          아직 Project Group이 없습니다.
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {groups.map((g) => (
            <li
              key={g.id}
              className="group relative rounded-md border p-4 transition-shadow hover:shadow-md"
              style={{
                background: "var(--color-surface)",
                borderColor: "var(--color-border)",
              }}
            >
              <Link href={`/groups/${g.id}`} className="block">
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-3 rounded-full"
                    style={{
                      background: g.color || "var(--color-accent)",
                    }}
                  />
                  <h3
                    className="text-base font-semibold"
                    style={{ color: "var(--color-text)" }}
                  >
                    {g.name}
                  </h3>
                  <span
                    className="rounded bg-[var(--color-bg-subtle)] px-2 py-0.5 text-[11px] font-medium"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    {g.status}
                  </span>
                </div>
                {g.description && (
                  <p
                    className="mt-2 text-sm line-clamp-2"
                    style={{ color: "var(--color-text-muted)" }}
                  >
                    {g.description}
                  </p>
                )}
                <p
                  className="mt-3 text-xs"
                  style={{ color: "var(--color-text-subtle)" }}
                >
                  {g.canvas_count} canvases
                  {g.default_environment
                    ? ` · ${g.default_environment.slug}`
                    : ""}
                  {g.default_aws_connection
                    ? ` · ${g.default_aws_connection.account_id}`
                    : ""}
                </p>
                {g.connected_aws_connections.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {g.connected_aws_connections.map((connection) => (
                      <span
                        key={connection.id}
                        className="rounded border px-2 py-0.5 text-[11px]"
                        style={{
                          borderColor: "var(--color-border)",
                          color: connection.is_default
                            ? "var(--color-accent)"
                            : "var(--color-text-muted)",
                        }}
                      >
                        {connection.account_id}
                        {connection.is_default ? " default" : ""}
                      </span>
                    ))}
                  </div>
                )}
                <p
                  className="mt-3 text-xs"
                  style={{ color: "var(--color-text-subtle)" }}
                >
                  Last activity{" "}
                  {g.last_activity_at
                    ? new Date(g.last_activity_at).toLocaleDateString()
                    : new Date(g.created_at).toLocaleDateString()}
                </p>
              </Link>
              <button
                onClick={() => setPendingDelete(g)}
                className="absolute right-3 top-3 hidden cursor-pointer rounded-md border px-2 py-1 text-xs font-medium transition-colors hover:bg-[var(--color-danger)]/10 group-hover:block"
                style={{
                  color: "var(--color-danger)",
                  borderColor: "var(--color-border)",
                }}
                aria-label="삭제"
              >
                삭제
              </button>
            </li>
          ))}
        </ul>
      )}

      {pendingDelete && (
        <ConfirmModal
          title="그룹 삭제"
          message={`'${pendingDelete.name}' Project Group을 휴지통으로 이동할까요?`}
          confirmLabel="삭제"
          cancelLabel="취소"
          onConfirm={handleDeleteConfirmed}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </main>
  );
}

function asMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "알 수 없는 오류";
}
