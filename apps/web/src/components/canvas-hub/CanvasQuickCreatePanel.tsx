import { useState, type ReactNode } from "react";
import Link from "next/link";
import {
  type ApiCanvasGroup,
  type AwsConnection,
  type CanvasKind,
  type CanvasTemplate,
  type Environment,
  type Target,
} from "@/lib/api";

type CanvasQuickCreatePanelProps = {
  loading: boolean;
  creating: boolean;
  templates: CanvasTemplate[];
  creatingTemplateId: string | null;
  groups: ApiCanvasGroup[];
  environments: Environment[];
  awsConnections: AwsConnection[];
  kubernetesTargets: Target[];
  selectedGroupId: string;
  selectedEnvironmentId: string;
  selectedAwsConnectionId: string;
  selectedKubernetesTargetId: string;
  sharedContextSummary: string;
  hasSharedContext: boolean;
  onGroupChange: (value: string) => void;
  onEnvironmentChange: (value: string) => void;
  onAwsConnectionChange: (value: string) => void;
  onKubernetesTargetChange: (value: string) => void;
  onCreateCanvas: (kind: Extract<CanvasKind, "aws" | "kubernetes">) => void;
  onCreateFromTemplate: (template: CanvasTemplate) => void;
};

export function CanvasQuickCreatePanel({
  loading,
  creating,
  templates,
  creatingTemplateId,
  groups,
  environments,
  awsConnections,
  kubernetesTargets,
  selectedGroupId,
  selectedEnvironmentId,
  selectedAwsConnectionId,
  selectedKubernetesTargetId,
  sharedContextSummary,
  hasSharedContext,
  onGroupChange,
  onEnvironmentChange,
  onAwsConnectionChange,
  onKubernetesTargetChange,
  onCreateCanvas,
  onCreateFromTemplate,
}: CanvasQuickCreatePanelProps) {
  const [selectedAwsTemplateId, setSelectedAwsTemplateId] = useState("");
  const [selectedKubernetesTemplateId, setSelectedKubernetesTemplateId] =
    useState("");
  const templateSections = buildTemplateSections(templates);
  const awsTemplates =
    templateSections.find((section) => section.id === "aws")?.templates || [];
  const kubernetesTemplates =
    templateSections.find((section) => section.id === "kubernetes")?.templates ||
    [];
  const selectedAwsTemplate = selectedAwsTemplateId
    ? awsTemplates.find((template) => template.id === selectedAwsTemplateId)
    : null;
  const selectedKubernetesTemplate = selectedKubernetesTemplateId
    ? kubernetesTemplates.find(
        (template) => template.id === selectedKubernetesTemplateId,
      )
    : null;
  const selectedAwsConnection = selectedAwsConnectionId
    ? awsConnections.find((connection) => connection.id === selectedAwsConnectionId)
    : null;
  const selectedKubernetesTarget = selectedKubernetesTargetId
    ? kubernetesTargets.find((target) => target.id === selectedKubernetesTargetId)
    : null;

  return (
    <section className="mb-5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--color-text)]">
          생성 컨텍스트
        </h2>
        <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
          공통 실행 범위만 먼저 고르고, 필요한 캔버스를 짧게 생성합니다.
        </p>
      </div>
      <div className="grid gap-3 border-b border-[var(--color-border)] p-4 lg:grid-cols-2">
        <ContextSelect
          label="Project Group"
          value={selectedGroupId}
          onChange={onGroupChange}
          emptyLabel={groups.length ? "미지정" : "Project Group 없음"}
          options={groups.map((group) => ({
            value: group.id,
            label: group.name,
            meta: group.default_environment?.slug || group.slug,
          }))}
        />
        <ContextSelect
          label="Environment"
          value={selectedEnvironmentId}
          onChange={onEnvironmentChange}
          emptyLabel={environments.length ? "기본값" : "Environment 없음"}
          options={environments.map((environment) => ({
            value: environment.id,
            label: environment.name,
            meta: `${environment.slug} · ${environment.risk_level}`,
          }))}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
        <div className="min-w-0 text-sm">
          <span className="font-medium text-[var(--color-text)]">
            공통 컨텍스트
          </span>
          <span className="ml-2 text-[var(--color-text-muted)]">
            {sharedContextSummary}
          </span>
          {!hasSharedContext && (
            <span className="ml-2 text-xs text-[var(--color-warning)]">
              Project Group / Environment 선택 권장
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/trash"
            className="flex h-9 items-center rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-4 text-sm font-medium text-[var(--color-text)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
          >
            휴지통
          </Link>
        </div>
      </div>

      <div className="divide-y divide-[var(--color-border)]">
        <QuickCreateRow
          title="AWS Canvas"
          meta={
            selectedAwsConnection
              ? `${selectedAwsConnection.name} · ${selectedAwsConnection.account_id}`
              : awsConnections.length
                ? "AWS Connection: 그룹 기본값"
                : "AWS Connection 없음"
          }
          selector={
            <div className="grid gap-2 md:grid-cols-2">
              <ContextSelect
                label="AWS Connection"
                value={selectedAwsConnectionId}
                onChange={onAwsConnectionChange}
                emptyLabel={awsConnections.length ? "그룹 기본값" : "AWS Connection 없음"}
                options={awsConnections.map((connection) => ({
                  value: connection.id,
                  label: connection.name,
                  meta: `${connection.account_id} / ${connection.default_region}`,
                }))}
              />
              <TemplateSelect
                label="템플릿"
                value={selectedAwsTemplateId}
                templates={awsTemplates}
                disabled={loading || awsTemplates.length === 0}
                onChange={setSelectedAwsTemplateId}
              />
            </div>
          }
          actionLabel={creating || creatingTemplateId ? "생성중..." : "생성"}
          disabled={creating || creatingTemplateId !== null}
          onCreate={() =>
            selectedAwsTemplate
              ? onCreateFromTemplate(selectedAwsTemplate)
              : onCreateCanvas("aws")
          }
        />
        <QuickCreateRow
          title="Kubernetes Canvas"
          meta={
            selectedKubernetesTarget
              ? `${selectedKubernetesTarget.name} · ${selectedKubernetesTarget.status}`
              : kubernetesTargets.length
                ? "Target 없이 초안 생성 가능"
                : "Kubernetes Target 없음"
          }
          selector={
            <div className="grid gap-2 md:grid-cols-2">
              <ContextSelect
                label="Kubernetes Target"
                value={selectedKubernetesTargetId}
                onChange={onKubernetesTargetChange}
                emptyLabel={
                  kubernetesTargets.length
                    ? "나중에 연결"
                    : "Kubernetes Target 없음"
                }
                options={kubernetesTargets.map((target) => ({
                  value: target.id,
                  label: target.name,
                  meta: `${target.status} · ${target.endpoint || "endpoint 없음"}`,
                }))}
              />
              <TemplateSelect
                label="템플릿"
                value={selectedKubernetesTemplateId}
                templates={kubernetesTemplates}
                disabled={loading || kubernetesTemplates.length === 0}
                onChange={setSelectedKubernetesTemplateId}
              />
            </div>
          }
          actionLabel={creating || creatingTemplateId ? "생성중..." : "생성"}
          disabled={creating || creatingTemplateId !== null}
          onCreate={() =>
            selectedKubernetesTemplate
              ? onCreateFromTemplate(selectedKubernetesTemplate)
              : onCreateCanvas("kubernetes")
          }
        />
        <div className="grid gap-3 px-4 py-3 text-sm md:grid-cols-[1fr_minmax(20rem,32rem)_6rem] md:items-center">
          <div className="min-w-0">
            <div className="font-semibold text-[var(--color-text)]">
              Multi-Architecture Canvas
            </div>
            <div className="mt-0.5 text-xs text-[var(--color-text-subtle)]">
              AWS 인프라와 Kubernetes 리소스 연결은 별도 UX로 설계 예정
            </div>
          </div>
          <div className="text-xs text-[var(--color-text-subtle)]">TODO</div>
          <button
            disabled
            className="h-9 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 text-sm text-[var(--color-text-subtle)]"
          >
            준비중
          </button>
        </div>
      </div>
    </section>
  );
}

type TemplateSectionModel = {
  id: string;
  title: string;
  description: string;
  templates: CanvasTemplate[];
};

function buildTemplateSections(
  templates: CanvasTemplate[],
): TemplateSectionModel[] {
  const sections: TemplateSectionModel[] = [
    {
      id: "aws",
      title: "AWS 템플릿",
      description: "VPC, EC2, RDS, S3 등 클라우드 인프라 시작점",
      templates: [],
    },
    {
      id: "kubernetes",
      title: "Kubernetes 템플릿",
      description: "Namespace, Deployment, Service 기반 워크로드 시작점",
      templates: [],
    },
    {
      id: "other",
      title: "기타 템플릿",
      description: "서비스 종류가 명확하지 않은 템플릿",
      templates: [],
    },
  ];
  const sectionById = new Map(sections.map((section) => [section.id, section]));
  for (const template of templates) {
    sectionById.get(inferTemplateSection(template))?.templates.push(template);
  }
  return sections;
}

function inferTemplateSection(template: CanvasTemplate) {
  const text = `${template.id} ${template.name} ${template.description}`.toLowerCase();
  if (text.includes("kubernetes") || text.includes("k8s")) return "kubernetes";
  if (
    text.includes("aws") ||
    text.includes("vpc") ||
    text.includes("ec2") ||
    text.includes("rds") ||
    text.includes("s3") ||
    text.includes("alb")
  ) {
    return "aws";
  }
  return "other";
}

function TemplateSelect({
  label,
  value,
  templates,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  templates: CanvasTemplate[];
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block min-w-[13rem]">
      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-text-subtle)]">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="h-9 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] disabled:cursor-not-allowed disabled:text-[var(--color-text-subtle)]"
      >
        <option value="">템플릿 선택</option>
        {templates.map((template) => (
          <option key={template.id} value={template.id}>
            {template.name} · 리소스 {template.node_count}개
          </option>
        ))}
      </select>
    </label>
  );
}

function QuickCreateRow({
  title,
  meta,
  selector,
  actionLabel,
  disabled,
  onCreate,
}: {
  title: string;
  meta: string;
  selector: ReactNode;
  actionLabel: string;
  disabled: boolean;
  onCreate: () => void;
}) {
  return (
    <div className="grid gap-3 px-4 py-3 md:grid-cols-[1fr_minmax(20rem,32rem)_6rem] md:items-center">
      <div className="min-w-0">
        <div className="font-semibold text-[var(--color-text)]">{title}</div>
        <div className="mt-0.5 truncate text-xs text-[var(--color-text-muted)]">
          {meta}
        </div>
      </div>
      <div>{selector}</div>
      <button
        onClick={onCreate}
        disabled={disabled}
        className={
          disabled
            ? "h-9 cursor-wait rounded-md bg-[var(--color-bg-subtle)] px-3 text-sm font-medium text-[var(--color-text-subtle)]"
            : "h-9 rounded-md bg-[var(--color-accent)] px-3 text-sm font-medium text-[var(--color-accent-fg)] shadow-[var(--shadow-sm)] hover:bg-[var(--color-accent-hover)]"
        }
      >
        {actionLabel}
      </button>
    </div>
  );
}

function ContextSelect({
  label,
  value,
  onChange,
  emptyLabel,
  options,
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  emptyLabel: string;
  options: Array<{ value: string; label: string; meta?: string | null }>;
  disabled?: boolean;
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-xs font-medium text-[var(--color-text-muted)]">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="h-10 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.meta ? `${option.label} · ${option.meta}` : option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
