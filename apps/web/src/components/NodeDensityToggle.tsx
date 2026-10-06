"use client";

import { useNodeDensity } from "@/lib/node-density-context";

/**
 * 노드 표기 밀도 토글 — 캔버스 헤더에 배치. 표준 ↔ 컴팩트.
 */
export function NodeDensityToggle() {
  const { density, setDensity } = useNodeDensity();
  const isCompact = density === "compact";
  return (
    <button
      onClick={() => setDensity(isCompact ? "standard" : "compact")}
      title={isCompact ? "표준 표기로 전환" : "컴팩트 표기로 전환"}
      className="rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text)] shadow-[var(--shadow-sm)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
    >
      {isCompact ? "컴팩트" : "표준"}
    </button>
  );
}
