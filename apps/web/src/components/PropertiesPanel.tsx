"use client";

import { type Node } from "@xyflow/react";
import { getNodeTypeDef } from "@/lib/node-types";
import { getGroupTypeDef, isGroupType } from "@/lib/group-types";
import {
  FormField,
  inputClass,
} from "@/components/properties/FormControls";
import { PropertiesForm } from "@/components/properties/ResourcePropertiesForm";

interface PropertiesUpdate {
  display_name?: string;
  properties?: Record<string, unknown>;
  view?: Record<string, unknown>;
}

type ContainmentItem = {
  id: string;
  name: string;
  type: string;
  color: string;
};

type SlotSecurityGroup = {
  id: string;
  name: string;
};

type SecurityGroupOption = SlotSecurityGroup;

const GROUP_LABEL_PT_OPTIONS = [8, 9, 10, 11, 12] as const;
const MIN_GROUP_LABEL_PT = 6;
const MAX_GROUP_LABEL_PT = 18;
const SECURITY_GROUP_ATTACHABLE_TYPES = new Set([
  "aws.ec2.instance",
  "aws.ec2.alb",
  "aws.rds.db_instance",
  "aws.ec2.asg",
]);

function normalizeGroupLabelPt(value: unknown): number {
  if (value === "xs") return 8;
  if (value === "sm") return 9;
  if (value === "md") return 10;
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string"
        ? Number(value)
        : NaN;
  if (Number.isFinite(parsed)) {
    return Math.min(MAX_GROUP_LABEL_PT, Math.max(MIN_GROUP_LABEL_PT, parsed));
  }
  return 9;
}

function clampGroupLabelPt(value: number): number {
  return Math.min(MAX_GROUP_LABEL_PT, Math.max(MIN_GROUP_LABEL_PT, value));
}

interface PropertiesPanelProps {
  node: Node;
  onChange: (nodeId: string, updates: PropertiesUpdate) => void;
  onClose: () => void;
  onToggleHidden: (nodeId: string, hidden: boolean) => void;
  securityGroupOptions: SecurityGroupOption[];
  onSecurityGroupToggle: (
    resourceId: string,
    securityGroupId: string,
    attached: boolean,
  ) => void;
  onSecurityGroupCreate: (resourceId: string) => void;
  onSecurityGroupSelect: (securityGroupId: string) => void;
}

export function PropertiesPanel({
  node,
  onChange,
  onClose,
  onToggleHidden,
  securityGroupOptions,
  onSecurityGroupToggle,
  onSecurityGroupCreate,
  onSecurityGroupSelect,
}: PropertiesPanelProps) {
  const isGroup = isGroupType(node.type);
  const isHidden = Boolean(node.data?.hidden);
  const nodeDef = getNodeTypeDef(node.type || "");
  const groupDef = getGroupTypeDef(node.type || "");
  const def = nodeDef || groupDef;
  const accentColor = isGroup
    ? groupDef?.borderColor || "var(--color-text-subtle)"
    : nodeDef?.color || "var(--color-text-subtle)";
  const props = (node.data?.properties as Record<string, unknown>) || {};
  const displayName = (node.data?.display_name as string) || "";
  const containment =
    (node.data?.containment as ContainmentItem[] | undefined) || [];
  const securityGroups =
    (node.data?.securityGroups as SlotSecurityGroup[] | undefined) || [];
  const supportsSecurityGroups = SECURITY_GROUP_ATTACHABLE_TYPES.has(node.type || "");

  function updateProperty(key: string, value: unknown) {
    onChange(node.id, {
      properties: { ...props, [key]: value },
    });
  }

  function updateDisplayName(value: string) {
    onChange(node.id, { display_name: value });
  }

  function updateGroupView(key: string, value: unknown) {
    onChange(node.id, { view: { [key]: value } });
  }

  return (
    <section className="min-h-full bg-[var(--color-surface)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
          {isGroup ? "영역 편집" : "속성 편집"}
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
        style={{ borderLeftColor: accentColor }}
      >
        {def?.displayName || "Unknown"}{" "}
        <span className="text-[var(--color-text-subtle)]">({node.type})</span>
      </div>

      <FormField label="이름 (display_name)">
        <input
          type="text"
          value={displayName}
          onChange={(e) => updateDisplayName(e.target.value)}
          className={inputClass}
        />
      </FormField>

      <ContainmentSection containment={containment} />
      {!isGroup && supportsSecurityGroups && (
        <SecurityGroupSection
          resourceId={node.id}
          selectedGroups={securityGroups}
          options={securityGroupOptions}
          onToggle={onSecurityGroupToggle}
          onCreate={onSecurityGroupCreate}
          onSelect={onSecurityGroupSelect}
        />
      )}

      {isGroup ? (
        <>
          <GroupDisplayForm node={node} onUpdate={updateGroupView} />
          <GroupForm
            groupType={node.type || ""}
            properties={props}
            onUpdate={updateProperty}
          />
        </>
      ) : (
        <PropertiesForm
          nodeType={node.type || ""}
          properties={props}
          onUpdate={updateProperty}
        />
      )}

      <div className="mt-5 border-t border-[var(--color-border)] pt-3">
        <button
          onClick={() => onToggleHidden(node.id, !isHidden)}
          className={
            isHidden
              ? "w-full rounded-md border border-[var(--color-accent)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-accent)] hover:bg-[var(--color-bg-subtle)]"
              : "w-full rounded-md border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-3 py-1.5 text-xs font-medium text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }
        >
          {isHidden ? "숨김 해제 — 다시 표시" : "이 리소스 숨기기"}
        </button>
        <p className="mt-1.5 text-[11px] leading-snug text-[var(--color-text-subtle)]">
          {isHidden
            ? "현재 숨김 상태. 헤더의 '숨긴 리소스 보기' 로 토글."
            : "서비스 이해에 불필요한 리소스를 뷰어에서 가림. .tf 생성에는 영향 없음."}
        </p>
      </div>
    </section>
  );
}

function SecurityGroupSection({
  resourceId,
  selectedGroups,
  options,
  onToggle,
  onCreate,
  onSelect,
}: {
  resourceId: string;
  selectedGroups: SlotSecurityGroup[];
  options: SecurityGroupOption[];
  onToggle: (
    resourceId: string,
    securityGroupId: string,
    attached: boolean,
  ) => void;
  onCreate: (resourceId: string) => void;
  onSelect: (securityGroupId: string) => void;
}) {
  const selectedIds = new Set(selectedGroups.map((group) => group.id));
  return (
    <div className="mt-3 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-2">
      <div className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">
        보안 그룹
      </div>
      {options.length === 0 ? (
        <div className="text-xs text-[var(--color-text-subtle)]">
          연결된 보안 그룹이 없습니다. 필요할 때 아래 버튼으로 이 리소스 전용 보안 그룹을 만들 수 있습니다.
        </div>
      ) : (
        <div className="space-y-1.5">
          {options.map((group) => (
            <div
              key={group.id}
              className="flex items-center justify-between gap-2 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-xs text-[var(--color-text)]"
            >
              <label className="flex min-w-0 flex-1 items-center gap-2">
                <input
                  type="checkbox"
                  checked={selectedIds.has(group.id)}
                  onChange={(event) =>
                    onToggle(resourceId, group.id, event.target.checked)
                  }
                  className="h-3.5 w-3.5 shrink-0 accent-[var(--color-accent)]"
                />
                <span className="min-w-0 truncate">{group.name}</span>
              </label>
              <button
                type="button"
                onClick={() => onSelect(group.id)}
                className="shrink-0 rounded border border-[var(--color-border)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
              >
                편집
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={() => onCreate(resourceId)}
        className="mt-2 w-full rounded border border-[var(--color-border-strong)] bg-[var(--color-surface)] px-2 py-1.5 text-xs font-medium text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
      >
        새 보안 그룹 생성
      </button>
      <div className="mt-1.5 text-[11px] leading-snug text-[var(--color-text-subtle)]">
        보안 그룹은 선택 사항입니다. 연결한 항목만 Plan 시 Security Group 참조로 변환됩니다.
      </div>
    </div>
  );
}

function ContainmentSection({
  containment,
}: {
  containment: ContainmentItem[];
}) {
  return (
    <div className="mt-3 rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-2">
      <div className="mb-1 text-xs font-medium text-[var(--color-text-muted)]">
        소속 영역
      </div>
      {containment.length === 0 ? (
        <div className="text-xs text-[var(--color-text-subtle)]">
          소속된 영역 없음
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <div className="truncate text-xs font-semibold text-[var(--color-text)]">
            {containment.map((item) => item.name).join(" > ")}
          </div>
          <div className="flex flex-wrap gap-1">
            {containment.map((item) => (
              <span
                key={item.id}
                className="max-w-full truncate rounded-sm px-1.5 py-0.5 text-[11px] font-medium text-white"
                style={{ background: item.color }}
                title={item.type}
              >
                {item.name}
              </span>
            ))}
          </div>
          <div className="text-[11px] leading-snug text-[var(--color-text-subtle)]">
            작은 영역부터 바깥 영역 순서
          </div>
        </div>
      )}
    </div>
  );
}

function GroupDisplayForm({
  node,
  onUpdate,
}: {
  node: Node;
  onUpdate: (key: string, value: unknown) => void;
}) {
  const groupLabelPt = normalizeGroupLabelPt(node.data?.groupLabelSize);
  const showCidr = node.data?.showCidr !== false;
  const showAz = node.data?.showAz !== false;

  return (
    <div className="mt-4 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2">
      <div className="mb-2 text-xs font-medium text-[var(--color-text-muted)]">
        영역 헤더 표기
      </div>
      <FormField label="글자 크기">
        <div className="grid grid-cols-[1fr_5.5rem] gap-2">
          <select
            value={
              GROUP_LABEL_PT_OPTIONS.some((pt) => pt === groupLabelPt)
                ? String(groupLabelPt)
                : "custom"
            }
            onChange={(e) => {
              if (e.target.value !== "custom") {
                onUpdate("groupLabelSize", Number(e.target.value));
              }
            }}
            className={inputClass}
          >
            {GROUP_LABEL_PT_OPTIONS.map((pt) => (
              <option key={pt} value={pt}>
                {pt}pt
              </option>
            ))}
            <option value="custom">직접</option>
          </select>
          <input
            type="number"
            min={MIN_GROUP_LABEL_PT}
            max={MAX_GROUP_LABEL_PT}
            step={0.5}
            value={groupLabelPt}
            onChange={(e) => {
              const next = Number(e.target.value);
              if (Number.isFinite(next)) {
                onUpdate("groupLabelSize", clampGroupLabelPt(next));
              }
            }}
            className={inputClass}
            aria-label="글자 크기 pt"
          />
        </div>
        <div className="mt-1 text-[11px] text-[var(--color-text-subtle)]">
          6pt-18pt 범위로 제한
        </div>
      </FormField>
      <label className="mt-3 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
        <input
          type="checkbox"
          checked={showCidr}
          onChange={(e) => onUpdate("showCidr", e.target.checked)}
        />
        CIDR 표시
      </label>
      <label className="mt-2 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
        <input
          type="checkbox"
          checked={showAz}
          onChange={(e) => onUpdate("showAz", e.target.checked)}
        />
        AZ 표시
      </label>
    </div>
  );
}

function GroupForm({
  groupType,
  properties,
  onUpdate,
}: {
  groupType: string;
  properties: Record<string, unknown>;
  onUpdate: (key: string, value: unknown) => void;
}) {
  if (groupType === "aws.ec2.vpc") {
    return (
      <>
        <FormField label="CIDR (cidr)">
          <input
            type="text"
            value={(properties.cidr as string) || ""}
            onChange={(e) => onUpdate("cidr", e.target.value)}
            placeholder="10.0.0.0/16"
            className={inputClass}
          />
        </FormField>
        <FormField label="리전 (region)">
          <input
            type="text"
            value={(properties.region as string) || ""}
            onChange={(e) => onUpdate("region", e.target.value)}
            placeholder="ap-northeast-2"
            className={inputClass}
          />
        </FormField>
      </>
    );
  }
  if (groupType === "aws.ec2.subnet") {
    return (
      <>
        <FormField label="CIDR (cidr)">
          <input
            type="text"
            value={(properties.cidr as string) || ""}
            onChange={(e) => onUpdate("cidr", e.target.value)}
            placeholder="10.0.1.0/24"
            className={inputClass}
          />
        </FormField>
        <FormField label="가용영역 (availability_zone)">
          <input
            type="text"
            value={(properties.availability_zone as string) || ""}
            onChange={(e) => onUpdate("availability_zone", e.target.value)}
            placeholder="ap-northeast-2a"
            className={inputClass}
          />
        </FormField>
        <FormField label="유형 (type)">
          <select
            value={(properties.type as string) || "private"}
            onChange={(e) => onUpdate("type", e.target.value)}
            className={inputClass}
          >
            <option value="public">public</option>
            <option value="private">private</option>
          </select>
        </FormField>
      </>
    );
  }
  return (
    <div className="mt-3 text-xs text-[var(--color-text-subtle)]">
      알 수 없는 영역 타입
    </div>
  );
}
