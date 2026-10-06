"use client";

import { type Edge } from "@xyflow/react";
import {
  EDGE_TYPES,
  DEFAULT_EDGE_KIND,
  getEdgeTypeDef,
} from "@/lib/edge-types";

interface EdgePropertiesUpdate {
  type?: string;
  properties?: Record<string, unknown>;
}

interface EdgePropertiesPanelProps {
  edge: Edge;
  onChange: (edgeId: string, updates: EdgePropertiesUpdate) => void;
  onClose: () => void;
}

const inputClass =
  "w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-sm text-[var(--color-text)] outline-none transition-colors focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent)]/20";

const labelClass =
  "mt-3 mb-1 block text-xs font-medium text-[var(--color-text-muted)]";

export function EdgePropertiesPanel({
  edge,
  onChange,
  onClose,
}: EdgePropertiesPanelProps) {
  const currentType = edge.type || DEFAULT_EDGE_KIND;
  const def = getEdgeTypeDef(currentType);
  const props =
    ((edge.data as { properties?: Record<string, unknown> } | undefined)
      ?.properties) || {};

  function updateProperty(key: string, value: unknown) {
    onChange(edge.id, {
      properties: { ...props, [key]: value },
    });
  }

  return (
    <section className="min-h-full bg-[var(--color-surface)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          연결 편집
        </h3>
        <button
          onClick={onClose}
          aria-label="닫기"
          className="rounded p-1 text-base leading-none text-[var(--color-text-subtle)] hover:bg-[var(--color-bg-subtle)] hover:text-[var(--color-text)]"
        >
          ✕
        </button>
      </div>

      <div
        className="mb-4 rounded border-l-4 bg-[var(--color-bg-subtle)] px-2.5 py-1.5 text-xs text-[var(--color-text-muted)]"
        style={{ borderLeftColor: def.color }}
      >
        {def.displayName}{" "}
        <span className="text-[var(--color-text-subtle)]">({def.type})</span>
        <div className="mt-1 text-[var(--color-text-subtle)]">
          {def.description}
        </div>
      </div>

      <label className={labelClass}>연결 종류 (type)</label>
      <div className="flex flex-col gap-1.5">
        {EDGE_TYPES.map((t) => (
          <label
            key={t.type}
            className={[
              "flex cursor-pointer items-center gap-2.5 rounded border px-2.5 py-1.5 text-sm transition-colors",
              currentType === t.type
                ? "border-[var(--color-accent)] bg-[var(--color-bg-subtle)]"
                : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]",
            ].join(" ")}
          >
            <input
              type="radio"
              name={`edge-type-${edge.id}`}
              value={t.type}
              checked={currentType === t.type}
              onChange={() => onChange(edge.id, { type: t.type })}
              className="accent-[var(--color-accent)]"
            />
            <span
              className="inline-block w-6 shrink-0"
              style={{
                height: `${Math.max(t.strokeWidth, 1.5)}px`,
                background: t.strokeDasharray
                  ? `repeating-linear-gradient(to right, ${t.color} 0 4px, transparent 4px 7px)`
                  : t.color,
              }}
            />
            <span className="flex-1">
              <span className="font-medium text-[var(--color-text)]">
                {t.displayName}
              </span>
              <span className="ml-1.5 text-xs text-[var(--color-text-subtle)]">
                {t.type}
              </span>
            </span>
          </label>
        ))}
      </div>

      <label className={labelClass}>라벨 (선택)</label>
      <input
        type="text"
        value={(props.label as string) || ""}
        onChange={(e) => updateProperty("label", e.target.value)}
        placeholder="HTTPS, 5432, ..."
        className={inputClass}
      />

      <label className={labelClass}>포트 / 범위 (port_range)</label>
      <input
        type="text"
        value={(props.port_range as string) || ""}
        onChange={(e) => updateProperty("port_range", e.target.value)}
        placeholder="443, 8080-8090"
        className={inputClass}
      />

      <label className={labelClass}>프로토콜 (protocol)</label>
      <select
        value={(props.protocol as string) || ""}
        onChange={(e) => updateProperty("protocol", e.target.value)}
        className={inputClass}
      >
        <option value="">(선택 안 함)</option>
        <option value="tcp">tcp</option>
        <option value="udp">udp</option>
        <option value="icmp">icmp</option>
        <option value="https">https</option>
        <option value="http">http</option>
      </select>
    </section>
  );
}
