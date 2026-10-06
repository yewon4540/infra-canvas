"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { CanvasFragment } from "@/lib/api";
import {
  ALL_NODE_TYPES,
  AWS_NODE_TYPES,
  KUBERNETES_NODE_TYPES,
  type AwsNodeTypeDef,
} from "@/lib/node-types";
import { AWS_GROUP_TYPES, type AwsGroupTypeDef } from "@/lib/group-types";

type PaletteSidebarProps = {
  collapsed: boolean;
  canvasKind: "aws" | "kubernetes" | "multi_architecture";
  fragments: CanvasFragment[];
  insertingFragment: boolean;
  onToggle: () => void;
  onInsertFragment: (fragmentId: string) => void;
};

type PaletteEntry = {
  type: string;
  label: string;
  sublabel: string;
  color: string;
  iconFile?: string;
  dragKind: "node" | "group";
  fragmentId?: string;
};

const CATEGORY_DEFS = [
  {
    id: "compute",
    platform: "AWS",
    label: "Compute",
    types: ["aws.ec2.instance", "aws.ec2.alb", "aws.ec2.asg"],
  },
  {
    id: "network",
    platform: "AWS",
    label: "Network",
    types: [
      "aws.ec2.vpc",
      "aws.ec2.subnet",
      "aws.ec2.internet_gateway",
      "aws.ec2.nat_gateway",
      "aws.ec2.route_table",
      "aws.route53.record",
    ],
  },
  {
    id: "storage",
    platform: "AWS",
    label: "Storage",
    types: ["aws.s3.bucket"],
  },
  {
    id: "database",
    platform: "AWS",
    label: "Database",
    types: ["aws.rds.db_instance"],
  },
  {
    id: "security",
    platform: "AWS",
    label: "Security",
    types: ["aws.iam.role"],
  },
  {
    id: "kubernetes-scope",
    platform: "Kubernetes",
    label: "Namespace / Scope",
    types: ["kubernetes.namespace"],
  },
  {
    id: "kubernetes-workloads",
    platform: "Kubernetes",
    label: "Workloads",
    types: ["kubernetes.deployment"],
  },
  {
    id: "kubernetes-network",
    platform: "Kubernetes",
    label: "Network / Exposition",
    types: ["kubernetes.service", "kubernetes.ingress"],
  },
  {
    id: "kubernetes-configuration",
    platform: "Kubernetes",
    label: "Configuration",
    types: ["kubernetes.config_map", "kubernetes.secret_ref"],
  },
  {
    id: "kubernetes-storage",
    platform: "Kubernetes",
    label: "Storage",
    types: ["kubernetes.pvc"],
  },
  {
    id: "kubernetes-rbac",
    platform: "Kubernetes",
    label: "RBAC / IAM",
    types: [],
  },
  {
    id: "kubernetes-policy",
    platform: "Kubernetes",
    label: "Resource Management / Policy",
    types: ["kubernetes.hpa"],
  },
];

export function PaletteSidebar({
  collapsed,
  canvasKind,
  fragments,
  insertingFragment,
  onToggle,
  onInsertFragment,
}: PaletteSidebarProps) {
  const [openCategories, setOpenCategories] = useState<Record<string, boolean>>({
    compute: true,
    network: true,
    storage: true,
    database: false,
    security: false,
    "kubernetes-scope": true,
    "kubernetes-workloads": true,
    "kubernetes-network": true,
    "kubernetes-configuration": false,
    "kubernetes-storage": false,
    "kubernetes-rbac": false,
    "kubernetes-policy": false,
  });
  const [openActionType, setOpenActionType] = useState<string | null>(null);

  const fragmentById = useMemo(
    () => new Map(fragments.map((fragment) => [fragment.id, fragment])),
    [fragments],
  );

  const entriesByType = useMemo(() => {
    const entries = new Map<string, PaletteEntry>();
    for (const groupType of AWS_GROUP_TYPES) {
      entries.set(groupType.type, {
        type: groupType.type,
        label: groupType.displayName,
        sublabel: groupType.englishName,
        color: groupType.borderColor,
        iconFile: groupType.iconFile,
        dragKind: "group",
        fragmentId: groupType.type === "aws.ec2.vpc" ? "vpc-basic-2az" : undefined,
      });
    }
    for (const nodeType of [...AWS_NODE_TYPES, ...KUBERNETES_NODE_TYPES]) {
      if (nodeType.presentation?.mode === "properties_slot") {
        continue;
      }
      entries.set(nodeType.type, {
        type: nodeType.type,
        label: nodeType.displayName,
        sublabel: nodeType.englishName,
        color: nodeType.color,
        iconFile: nodeType.iconFile,
        dragKind: "node",
      });
    }
    return entries;
  }, []);

  const visibleCategories = CATEGORY_DEFS.filter((category) => {
    if (canvasKind === "multi_architecture") return true;
    return category.platform === (canvasKind === "aws" ? "AWS" : "Kubernetes");
  });

  function onDragStart(event: React.DragEvent, nodeType: AwsNodeTypeDef) {
    event.dataTransfer.setData("application/eolgae-node", nodeType.type);
    event.dataTransfer.effectAllowed = "move";
  }

  function onGroupDragStart(event: React.DragEvent, groupType: AwsGroupTypeDef) {
    event.dataTransfer.setData("application/eolgae-node", groupType.type);
    event.dataTransfer.effectAllowed = "move";
  }

  function onEntryDragStart(event: React.DragEvent, entry: PaletteEntry) {
    if (entry.dragKind === "group") {
      const groupType = AWS_GROUP_TYPES.find((item) => item.type === entry.type);
      if (groupType) onGroupDragStart(event, groupType);
      return;
    }
    const nodeType = ALL_NODE_TYPES.find((item) => item.type === entry.type);
    if (nodeType) onDragStart(event, nodeType);
  }

  function toggleCategory(categoryId: string) {
    setOpenCategories((current) => ({
      ...current,
      [categoryId]: !current[categoryId],
    }));
  }

  function handleInsertFragment(fragmentId: string) {
    setOpenActionType(null);
    onInsertFragment(fragmentId);
  }

  return (
    <aside
      className={
        collapsed
          ? "flex w-12 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-subtle)]"
          : "flex w-60 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg-subtle)]"
      }
    >
      <Link
        href="/canvas"
        title="홈으로"
        className={
          collapsed
            ? "flex h-12 items-center justify-center border-b border-[var(--color-border)] transition-colors hover:bg-[var(--color-accent-soft)]"
            : "flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-3 transition-colors hover:bg-[var(--color-accent-soft)]"
        }
      >
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: "var(--color-accent)" }}
          aria-hidden
        />
        {!collapsed && (
          <>
            <span className="text-base font-bold tracking-tight text-[var(--color-text)]">
              Eolgae
            </span>
            <span className="ml-auto text-xs text-[var(--color-text-subtle)]">
              홈
            </span>
          </>
        )}
      </Link>

      <button
        onClick={onToggle}
        title={collapsed ? "컴포넌트 팔레트 열기" : "컴포넌트 팔레트 닫기"}
        className={
          collapsed
            ? "flex h-10 items-center justify-center border-b border-[var(--color-border)] text-sm text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
            : "mx-3 mt-3 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
        }
      >
        {collapsed ? "›" : "‹ 팔레트 접기"}
      </button>

      {collapsed ? (
        <div className="flex flex-1 items-start justify-center pt-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-text-subtle)] [writing-mode:vertical-rl]">
          Components
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            Resources
          </h3>
          <p className="mb-3 text-xs text-[var(--color-text-subtle)]">
            컴포넌트는 드래그, 기본 구성은 항목 메뉴에서 추가
          </p>

          <div className="flex flex-col gap-2">
            {visibleCategories.map((category) => {
              const open = openCategories[category.id] ?? true;
              const entries = category.types
                .map((type) => entriesByType.get(type))
                .filter((entry): entry is PaletteEntry => Boolean(entry));
              return (
                <section
                  key={category.id}
                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]"
                >
                  <button
                    type="button"
                    onClick={() => toggleCategory(category.id)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] hover:bg-[var(--color-bg-subtle)]"
                  >
                    <span className="w-3 text-[var(--color-text-subtle)]">
                      {open ? "⌄" : "›"}
                    </span>
                    {category.platform} - {category.label}
                  </button>
                  {open && (
                    <div className="border-t border-[var(--color-border)] p-1.5">
                      {entries.length === 0 ? (
                        <div className="px-2 py-2 text-xs text-[var(--color-text-subtle)]">
                          TODO: future resource types
                        </div>
                      ) : (
                        entries.map((entry) => (
                          <PaletteEntryRow
                            key={entry.type}
                            entry={entry}
                            fragment={entry.fragmentId ? fragmentById.get(entry.fragmentId) : undefined}
                            menuOpen={openActionType === entry.type}
                            insertingFragment={insertingFragment}
                            onDragStart={onEntryDragStart}
                            onMenuToggle={() =>
                              setOpenActionType((current) =>
                                current === entry.type ? null : entry.type,
                              )
                            }
                            onInsertFragment={handleInsertFragment}
                          />
                        ))
                      )}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </aside>
  );
}

function PaletteEntryRow({
  entry,
  fragment,
  menuOpen,
  insertingFragment,
  onDragStart,
  onMenuToggle,
  onInsertFragment,
}: {
  entry: PaletteEntry;
  fragment?: CanvasFragment;
  menuOpen: boolean;
  insertingFragment: boolean;
  onDragStart: (event: React.DragEvent, entry: PaletteEntry) => void;
  onMenuToggle: () => void;
  onInsertFragment: (fragmentId: string) => void;
}) {
  return (
    <div className="relative">
      <div
        draggable
        onDragStart={(event) => onDragStart(event, entry)}
        className="group flex cursor-grab items-center gap-2 rounded px-2 py-2 transition-colors hover:bg-[var(--color-bg-subtle)] active:cursor-grabbing"
      >
        {entry.iconFile ? (
          <div
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded"
            style={{ background: `${entry.color}14` }}
          >
            <img
              src={`/icons/aws/${entry.iconFile}`}
              alt={entry.sublabel}
              width={22}
              height={22}
            />
          </div>
        ) : (
          <div
            className="h-2 w-2 shrink-0 rounded-full"
            style={{ background: entry.color }}
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-[var(--color-text)]">
            {entry.label}
          </div>
          <div className="truncate text-xs text-[var(--color-text-subtle)]">
            {entry.sublabel}
          </div>
        </div>
        {fragment && (
          <button
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onMenuToggle();
            }}
            onDragStart={(event) => event.preventDefault()}
            className="shrink-0 rounded border border-[var(--color-border)] px-1.5 py-1 text-xs text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
            title="추가 방식 선택"
          >
            ⋯
          </button>
        )}
      </div>
      {fragment && menuOpen && (
        <div className="absolute right-1 top-10 z-20 w-52 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-1.5 shadow-[var(--shadow-lg)]">
          <div className="px-2 py-1.5 text-xs text-[var(--color-text-subtle)]">
            단일 추가는 항목을 드래그
          </div>
          <button
            type="button"
            disabled={insertingFragment}
            onClick={() => onInsertFragment(fragment.id)}
            className="block w-full rounded px-2 py-2 text-left text-sm font-medium text-[var(--color-text)] hover:bg-[var(--color-bg-subtle)] disabled:cursor-not-allowed disabled:opacity-45"
          >
            {fragment.name}
          </button>
        </div>
      )}
    </div>
  );
}
