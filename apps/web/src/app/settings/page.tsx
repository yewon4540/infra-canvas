"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { WorkspaceHeader, WorkspaceShell } from "@/components/WorkspaceShell";
import { getRuntimeSettings, type RuntimeSettings } from "@/lib/api";

const storagePurpose = [
  "OpenTofu main.tf / tfplan 영구 보관",
  "Plan / Apply 재현과 감사 추적",
  "아키텍처 구조도 이미지 다운로드",
  "PPT / 문서형 산출물 다운로드",
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRuntimeSettings()
      .then(setSettings)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const storage = settings?.artifact_storage;

  return (
    <WorkspaceShell active="settings">
      <div className="mx-auto max-w-5xl">
      <WorkspaceHeader
        title="환경설정"
        description="계정 연결, 캔버스 그룹, 산출물 저장소를 관리합니다."
      />

      <SettingsSection title="Active">
        <SettingsLink
          title="AWS Connections"
          description="여러 Project Group과 Canvas에서 재사용할 AWS 계정 Role 연결을 관리합니다."
          href="/aws-connections"
          meta="Read-only, Plan-ready, Apply-enabled"
        />
        <SettingsLink
          title="Project Groups"
          description="캔버스, AWS 연결, 배포 이력을 업무/프로젝트 단위로 묶습니다."
          href="/groups"
          meta="Work grouping"
        />
        <SettingsLink
          title="Environments"
          description="dev, stg, prd, shared, sandbox 같은 실행 환경과 위험도를 관리합니다."
          href="/environments"
          meta="Risk level"
        />
        <SettingsLink
          title="Targets"
          description="AWS Account와 Kubernetes Cluster를 공통 운영 대상으로 관리합니다."
          href="/targets"
          meta="AWS, Kubernetes"
        />
        <SettingsPlaceholder
          title="Audit Logs"
          description="사용자 행위와 승인/변경 이력을 제품 기능으로 조회합니다."
          meta="Read-only"
        />
        <SettingsPlaceholder
          title="System Logs"
          description="worker, plan/apply 실행, integration 상태 같은 시스템 로그를 분리해 봅니다."
          meta="Read-only"
        />
      </SettingsSection>

      <SettingsSection title="Preview">
        <SettingsPlaceholder
          title="Execution Policies"
          description="Environment와 Project Group 기준으로 Plan/Apply/Destroy 허용 범위를 정의합니다."
          meta="Preview"
        />
        <SettingsPlaceholder
          title="Approval Policies"
          description="prd, destroy, high-risk 변경에 대한 승인 조건을 정의합니다."
          meta="Preview"
        />
        <SettingsPlaceholder
          title="AI Settings"
          description="AI 리뷰 기준, 위험도 해석, context redaction 정책을 조정합니다."
          meta="Preview"
        />
      </SettingsSection>

      <SettingsSection title="Coming Soon">
        {[
          "Integrations",
          "Users / Roles",
          "Capabilities",
          "Feature Flags",
          "License",
        ].map((title) => (
          <SettingsPlaceholder
            key={title}
            title={title}
            description="후속 운영관리 범위에서 활성화됩니다."
            meta="Coming Soon"
          />
        ))}
      </SettingsSection>

      <section className="mt-5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[var(--color-text)]">
              스토리지
            </h2>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              배포 산출물과 다운로드 파일을 저장하는 backend입니다.
            </p>
          </div>
          {storage && (
            <span className="rounded bg-[var(--color-accent-soft)] px-2 py-1 text-xs font-medium text-[var(--color-accent)]">
              {storage.backend}
            </span>
          )}
        </div>

        {error && (
          <p className="mt-4 text-sm text-[var(--color-danger)]">오류: {error}</p>
        )}

        {loading ? (
          <p className="mt-5 text-sm text-[var(--color-text-subtle)]">로딩 중...</p>
        ) : storage ? (
          <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
            <div className="space-y-2">
              <SettingRow label="Backend" value={storage.backend} />
              <SettingRow label="Retention" value={storage.retention_policy} />
              {storage.backend === "local" ? (
                <SettingRow label="Local root" value={storage.local_root || "-"} />
              ) : (
                <>
                  <SettingRow label="Bucket" value={storage.s3_bucket || "-"} />
                  <SettingRow label="Prefix" value={storage.s3_prefix || "-"} />
                  <SettingRow label="Region" value={storage.s3_region || "-"} />
                  <SettingRow
                    label="Endpoint"
                    value={storage.s3_endpoint_url || "AWS S3 default"}
                  />
                  <SettingRow
                    label="Path style"
                    value={storage.s3_force_path_style ? "enabled" : "disabled"}
                  />
                </>
              )}
            </div>

            <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-4">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">
                저장 대상
              </h3>
              <ul className="mt-3 space-y-2 text-sm text-[var(--color-text-muted)]">
                {storagePurpose.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-accent)]" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <p className="mt-5 text-sm text-[var(--color-text-subtle)]">
            스토리지 설정을 불러오지 못했습니다.
          </p>
        )}
      </section>
      </div>
    </WorkspaceShell>
  );
}

function SettingsLink({
  title,
  description,
  href,
  meta,
}: {
  title: string;
  description: string;
  href: string;
  meta: string;
}) {
  return (
    <Link
      href={href}
      className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-5 transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]"
    >
      <span className="text-xs font-medium uppercase text-[var(--color-text-subtle)]">
        {meta}
      </span>
      <h2 className="mt-2 text-base font-semibold text-[var(--color-text)]">
        {title}
      </h2>
      <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
        {description}
      </p>
    </Link>
  );
}

function SettingsSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5">
      <h2 className="mb-2 text-sm font-semibold text-[var(--color-text-muted)]">
        {title}
      </h2>
      <div className="grid gap-3 md:grid-cols-2">{children}</div>
    </section>
  );
}

function SettingsPlaceholder({
  title,
  description,
  meta,
}: {
  title: string;
  description: string;
  meta: string;
}) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-5">
      <span className="text-xs font-medium uppercase text-[var(--color-text-subtle)]">
        {meta}
      </span>
      <h3 className="mt-2 text-base font-semibold text-[var(--color-text)]">
        {title}
      </h3>
      <p className="mt-1 text-sm leading-6 text-[var(--color-text-muted)]">
        {description}
      </p>
    </div>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-3 border-b border-[var(--color-border)] py-2 text-sm last:border-b-0">
      <span className="text-[var(--color-text-subtle)]">{label}</span>
      <span className="min-w-0 break-words font-medium text-[var(--color-text)]">
        {value}
      </span>
    </div>
  );
}
