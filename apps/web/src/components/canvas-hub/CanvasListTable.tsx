import Link from "next/link";
import {
  type ApiCanvasGroup,
  type AwsConnection,
  type Canvas,
  type CanvasKind,
  type CanvasState,
  type Environment,
  type Target,
} from "@/lib/api";

export type CanvasFilter = "all" | "design" | "applied" | "destroyed";

const CANVAS_KIND_LABELS: Record<CanvasKind, string> = {
  aws: "AWS",
  kubernetes: "Kubernetes",
  multi_architecture: "Multi-Architecture",
};

const STATE_LABELS: Record<CanvasState, string> = {
  design: "Design",
  deploy: "Apply",
  running: "Apply",
  applied: "Apply",
  destroyed: "Destroy",
};

const STATE_COLORS: Record<CanvasState, string> = {
  design: "var(--color-text-muted)",
  deploy: "var(--color-warning)",
  running: "var(--color-success)",
  applied: "var(--color-success)",
  destroyed: "var(--color-text-subtle)",
};

type CanvasListTableProps = {
  filteredCanvases: Canvas[];
  loading: boolean;
  filter: CanvasFilter;
  counts: Record<CanvasFilter, number>;
  groups: Map<string, ApiCanvasGroup>;
  environments: Map<string, Environment>;
  awsConnections: Map<string, AwsConnection>;
  kubernetesTargets: Map<string, Target>;
  duplicatingId: string | null;
  onFilterChange: (filter: CanvasFilter) => void;
  onRename: (id: string, currentName: string) => void;
  onDuplicate: (canvas: Canvas) => void;
  onDelete: (canvas: Canvas) => void;
};

export function CanvasListTable({
  filteredCanvases,
  loading,
  filter,
  counts,
  groups,
  environments,
  awsConnections,
  kubernetesTargets,
  duplicatingId,
  onFilterChange,
  onRename,
  onDuplicate,
  onDelete,
}: CanvasListTableProps) {
  return (
    <>
      <div
        id="canvas-list"
        className="mb-4 flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex gap-1">
          <FilterChip
            label="전체"
            count={counts.all}
            active={filter === "all"}
            onClick={() => onFilterChange("all")}
          />
          <FilterChip
            label="Design"
            count={counts.design}
            active={filter === "design"}
            onClick={() => onFilterChange("design")}
          />
          <FilterChip
            label="Apply"
            count={counts.applied}
            active={filter === "applied"}
            onClick={() => onFilterChange("applied")}
          />
          <FilterChip
            label="Destroy"
            count={counts.destroyed}
            active={filter === "destroyed"}
            onClick={() => onFilterChange("destroyed")}
          />
        </div>
      </div>

      {loading ? (
        <div className="p-10 text-center text-sm text-[var(--color-text-subtle)]">
          로딩중...
        </div>
      ) : filteredCanvases.length === 0 ? (
        <div className="rounded-md border border-dashed border-[var(--color-border-strong)] p-10 text-center text-sm text-[var(--color-text-muted)]">
          {filter === "all"
            ? "캔버스 없음. 생성 컨텍스트를 확인한 뒤 새 캔버스로 시작하세요."
            : `${STATE_LABELS[filter as CanvasState]} 상태인 캔버스 없음.`}
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
          <table className="w-full border-collapse text-sm">
            <thead className="bg-[var(--color-bg-subtle)] text-left text-xs font-medium uppercase text-[var(--color-text-subtle)]">
              <tr>
                <th className="px-4 py-2">Canvas</th>
                <th className="px-4 py-2">Type</th>
                <th className="px-4 py-2">State</th>
                <th className="px-4 py-2">Project Group</th>
                <th className="px-4 py-2">Environment</th>
                <th className="px-4 py-2">Connection / Target</th>
                <th className="px-4 py-2">Updated</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCanvases.map((canvas) => {
                const group = canvas.group_id ? groups.get(canvas.group_id) : null;
                const environment = canvas.environment_id
                  ? environments.get(canvas.environment_id)
                  : null;
                const awsConnection = canvas.aws_connection_id
                  ? awsConnections.get(canvas.aws_connection_id)
                  : null;
                const kubernetesTarget = canvas.target_id
                  ? kubernetesTargets.get(canvas.target_id)
                  : null;
                return (
                  <tr
                    key={canvas.id}
                    className="border-t border-[var(--color-border)] hover:bg-[var(--color-bg-subtle)]"
                  >
                    <td className="min-w-[16rem] px-4 py-3">
                      <Link
                        href={`/canvas/${canvas.id}`}
                        className="font-semibold text-[var(--color-text)] hover:text-[var(--color-accent)] hover:underline"
                      >
                        {canvas.name}
                      </Link>
                      <div className="mt-0.5 max-w-[24rem] truncate text-xs text-[var(--color-text-subtle)]">
                        {canvas.description || canvas.id}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      {CANVAS_KIND_LABELS[canvas.canvas_kind || "aws"]}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex min-w-16 justify-center rounded px-2 py-0.5 text-xs font-semibold text-white"
                        style={{ background: STATE_COLORS[canvas.state] }}
                      >
                        {STATE_LABELS[canvas.state]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <TableMeta
                        primary={group?.name || "미지정"}
                        secondary={group?.slug}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <TableMeta
                        primary={environment?.slug || "미지정"}
                        secondary={environment?.risk_level}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <TableMeta
                        primary={
                          canvas.canvas_kind === "kubernetes"
                            ? kubernetesTarget?.name || "미지정"
                            : awsConnection?.name || "미지정"
                        }
                        secondary={
                          canvas.canvas_kind === "kubernetes"
                            ? kubernetesTarget?.endpoint ||
                              kubernetesTarget?.status
                            : awsConnection
                              ? `${awsConnection.account_id} / ${awsConnection.default_region}`
                              : undefined
                        }
                      />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-[var(--color-text-muted)]">
                      {new Date(canvas.updated_at).toLocaleString("ko-KR")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => onRename(canvas.id, canvas.name)}
                          title="이름 변경"
                          className="rounded border border-[var(--color-border)] px-2 py-1 text-xs text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
                        >
                          이름
                        </button>
                        <button
                          onClick={() => onDuplicate(canvas)}
                          disabled={duplicatingId === canvas.id}
                          title="캔버스 복제"
                          className="rounded border border-[var(--color-border)] px-2 py-1 text-xs text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)] disabled:cursor-wait disabled:text-[var(--color-text-subtle)]"
                        >
                          {duplicatingId === canvas.id ? "복제중" : "복제"}
                        </button>
                        <button
                          onClick={() => onDelete(canvas)}
                          title="캔버스 삭제 (휴지통으로 이동)"
                          className="rounded border border-[var(--color-border)] px-2 py-1 text-xs text-[var(--color-text-subtle)] hover:border-[var(--color-danger)] hover:text-[var(--color-danger)]"
                        >
                          삭제
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function TableMeta({
  primary,
  secondary,
}: {
  primary: string;
  secondary?: string | null;
}) {
  return (
    <div className="min-w-0">
      <div className="max-w-[12rem] truncate text-sm font-medium text-[var(--color-text)]">
        {primary}
      </div>
      {secondary && (
        <div className="mt-0.5 max-w-[12rem] truncate text-xs text-[var(--color-text-subtle)]">
          {secondary}
        </div>
      )}
    </div>
  );
}

function FilterChip({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  const base = "rounded-md border px-3 py-1.5 text-xs transition-colors";
  if (active) {
    return (
      <button
        onClick={onClick}
        className={`${base} border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-accent-fg)]`}
      >
        {label} ({count})
      </button>
    );
  }
  return (
    <button
      onClick={onClick}
      className={`${base} border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]`}
    >
      {label} ({count})
    </button>
  );
}
