"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import {
  createEnvironment,
  listEnvironments,
  type Environment,
} from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { UserMenu } from "@/components/UserMenu";

const riskLabels = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

export default function EnvironmentsPage() {
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [riskLevel, setRiskLevel] = useState<"low" | "medium" | "high">("low");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    listEnvironments()
      .then(setEnvironments)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createEnvironment({
        name: name.trim(),
        slug: slug.trim() || undefined,
        risk_level: riskLevel,
      });
      setEnvironments((prev) => [...prev, created]);
      setName("");
      setSlug("");
      setRiskLevel("low");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link
            href="/settings"
            className="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:underline"
          >
            환경설정
          </Link>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-[var(--color-text)]">
            Environments
          </h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            실행 환경과 위험도를 관리합니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <UserMenu />
          <ThemeToggle />
        </div>
      </div>

      <form
        onSubmit={handleCreate}
        className="mb-5 grid gap-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3 md:grid-cols-[1fr_160px_150px_auto]"
      >
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Environment name"
          className="rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none"
        />
        <input
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="slug"
          className="rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none"
        />
        <select
          value={riskLevel}
          onChange={(event) =>
            setRiskLevel(event.target.value as "low" | "medium" | "high")
          }
          className="rounded border border-[var(--color-border-strong)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none"
        >
          <option value="low">Low risk</option>
          <option value="medium">Medium risk</option>
          <option value="high">High risk</option>
        </select>
        <button
          disabled={creating || !name.trim()}
          className="rounded-md bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-accent-fg)] disabled:opacity-50"
        >
          {creating ? "생성 중" : "생성"}
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-[var(--color-danger)]">{error}</p>}

      {loading ? (
        <p className="text-sm text-[var(--color-text-muted)]">로딩 중...</p>
      ) : (
        <div className="overflow-hidden rounded-md border border-[var(--color-border)]">
          <table className="w-full border-collapse bg-[var(--color-surface)] text-sm">
            <thead className="bg-[var(--color-bg-subtle)] text-left text-[var(--color-text-muted)]">
              <tr>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Slug</th>
                <th className="px-4 py-2 font-medium">Risk</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {environments.map((environment) => (
                <tr
                  key={environment.id}
                  className="border-t border-[var(--color-border)]"
                >
                  <td className="px-4 py-3 font-medium text-[var(--color-text)]">
                    {environment.name}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">
                    {environment.slug}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">
                    {riskLabels[environment.risk_level]}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">
                    {environment.archived_at ? "Archived" : "Active"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
