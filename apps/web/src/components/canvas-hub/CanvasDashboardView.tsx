import {
  type Canvas,
  type DeploymentSummary,
  type DeploymentSummaryItem,
} from "@/lib/api";
import { WorkspaceHeader } from "@/components/WorkspaceShell";

type CanvasDashboardViewProps = {
  canvases: Canvas[];
  applyCount: number;
  destroyCount: number;
  designCount: number;
  awsConnectionCount: number;
  kubernetesTargetCount: number;
  environmentCount: number;
  deploymentSummary: DeploymentSummary | null;
};

export function CanvasDashboardView({
  canvases,
  applyCount,
  destroyCount,
  designCount,
  awsConnectionCount,
  kubernetesTargetCount,
  environmentCount,
  deploymentSummary,
}: CanvasDashboardViewProps) {
  const awsCount = canvases.filter((c) => c.canvas_kind === "aws").length;
  const kubernetesCount = canvases.filter(
    (c) => c.canvas_kind === "kubernetes",
  ).length;
  const recentRuns = deploymentSummary?.recent || [];
  const dashboardItems = [
    {
      // label: "Apply"
      label: "구축",
      value: applyCount,
      // hint: "applied / running / deploy"
      hint: "적용 / 실행 / 배포 상태",
      tone: "success",
    },
    {
      // label: "Destroy"
      label: "삭제",
      value: destroyCount,
      // hint: "destroyed canvases"
      hint: "삭제 완료된 캔버스",
      tone: "muted",
    },
    {
      // label: "Design"
      label: "설계",
      value: designCount,
      // hint: "draft work"
      hint: "초안 작업",
      tone: "warning",
    },
    {
      // label: "Total"
      label: "전체",
      value: canvases.length,
      hint: `${awsCount} AWS / ${kubernetesCount} K8s`,
      tone: "accent",
    },
  ];

  return (
    <>
      <WorkspaceHeader
        // title="Dashboard"
        title="대시보드"
        description="운영 상태를 먼저 확인하고, 필요한 캔버스 작업으로 바로 이동합니다."
      />
      <section className="mb-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {dashboardItems.map((item) => (
          <DashboardMetric
            key={item.label}
            label={item.label}
            value={item.value}
            hint={item.hint}
            tone={item.tone}
          />
        ))}
      </section>
      <section className="grid gap-4 xl:grid-cols-3">
        {/* title="Execution" */}
        <DashboardPanel title="실행">
          {/* label="Apply-ready" */}
          <DashboardRow label="구축 가능" value={applyCount} />
          {/* label="Destroy complete" */}
          <DashboardRow label="삭제 완료" value={destroyCount} />
          {/* label="Draft designs" */}
          <DashboardRow label="설계 초안" value={designCount} />
        </DashboardPanel>
        {/* title="Targets" */}
        <DashboardPanel title="대상">
          {/* label="AWS Connections" */}
          <DashboardRow label="AWS 연결" value={awsConnectionCount} />
          {/* label="Kubernetes Targets" */}
          <DashboardRow
            label="Kubernetes 대상"
            value={kubernetesTargetCount}
          />
          {/* label="Environments" */}
          <DashboardRow label="환경" value={environmentCount} />
        </DashboardPanel>
        {/* title="Operations" */}
        <DashboardPanel title="운영">
          {/* label="Approval pending" */}
          <DashboardRow
            label="승인 대기"
            value={deploymentSummary?.approval_pending ?? 0}
          />
          {/* label="Failed runs" */}
          <DashboardRow label="실패 실행" value={deploymentSummary?.failed ?? 0} />
          {/* label="Active runs" */}
          <DashboardRow label="진행 중" value={deploymentSummary?.active ?? 0} />
        </DashboardPanel>
      </section>
      <section className="mt-4 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">
            {/* Recent Runs */}
            최근 실행
          </h2>
          <span className="text-xs text-[var(--color-text-subtle)]">
            {/* Plan / Apply / Destroy */}
            계획 / 구축 / 삭제
          </span>
        </div>
        {recentRuns.length === 0 ? (
          <div className="px-4 py-5 text-sm text-[var(--color-text-muted)]">
            아직 실행 이력이 없습니다.
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {recentRuns.map((run) => (
              <RecentRunRow key={run.id} run={run} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function DashboardMetric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
  tone: string;
}) {
  const toneColor =
    tone === "success"
      ? "var(--color-success)"
      : tone === "warning"
        ? "var(--color-warning)"
        : tone === "accent"
          ? "var(--color-accent)"
          : "var(--color-text-muted)";

  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-subtle)]">
          {label}
        </div>
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{ background: toneColor }}
        />
      </div>
      <div className="mt-3 text-3xl font-semibold text-[var(--color-text)]">
        {value}
      </div>
      <div className="mt-1 truncate text-xs text-[var(--color-text-muted)]">
        {hint}
      </div>
    </div>
  );
}

function DashboardPanel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--color-text)]">
          {title}
        </h2>
      </div>
      <div className="divide-y divide-[var(--color-border)]">{children}</div>
    </section>
  );
}

function DashboardRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3">
      <span className="text-sm text-[var(--color-text-muted)]">{label}</span>
      <span className="text-sm font-semibold text-[var(--color-text)]">
        {value}
      </span>
    </div>
  );
}

function RecentRunRow({ run }: { run: DeploymentSummaryItem }) {
  return (
    <div className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[8rem_8rem_1fr_9rem] md:items-center">
      <div className="font-semibold uppercase text-[var(--color-text)]">
        {runModeLabel(run.mode)}
      </div>
      <StatusPill status={run.status} />
      <div className="min-w-0">
        <div className="truncate text-[var(--color-text-muted)]">
          canvas {run.canvas_id.slice(0, 8)}
        </div>
        {run.error_message && (
          <div className="mt-0.5 truncate text-xs text-[var(--color-danger)]">
            {run.error_message}
          </div>
        )}
      </div>
      <div className="text-xs text-[var(--color-text-subtle)]">
        {formatRunTime(run.created_at)}
      </div>
    </div>
  );
}

function runModeLabel(mode: DeploymentSummaryItem["mode"]) {
  // plan/apply/destroy
  if (mode === "plan") return "계획";
  if (mode === "apply") return "구축";
  if (mode === "destroy") return "삭제";
  return mode;
}

function StatusPill({ status }: { status: DeploymentSummaryItem["status"] }) {
  const color =
    status === "failed"
      ? "var(--color-danger)"
      : status === "success" || status === "approved"
        ? "var(--color-warning)"
        : status === "applied" || status === "destroyed"
          ? "var(--color-success)"
          : "var(--color-accent)";
  return (
    <span
      className="w-fit rounded border px-2 py-1 text-xs font-medium"
      style={{
        borderColor: color,
        color,
      }}
    >
      {statusLabel(status)}
    </span>
  );
}

function statusLabel(status: DeploymentSummaryItem["status"]) {
  // queued/planning/success/approved/applying/applied/destroying/destroyed/failed
  if (status === "queued") return "대기";
  if (status === "planning") return "계획 중";
  if (status === "success") return "승인 대기";
  if (status === "approved") return "승인됨";
  if (status === "applying") return "구축 중";
  if (status === "applied") return "구축 완료";
  if (status === "destroying") return "삭제 중";
  if (status === "destroyed") return "삭제 완료";
  if (status === "failed") return "실패";
  return status;
}

function formatRunTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
