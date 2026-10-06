"use client";

import type { CSSProperties } from "react";
import { Handle, NodeResizer, Position, type NodeProps } from "@xyflow/react";
import { ALL_NODE_TYPES, getNodeTypeDef } from "@/lib/node-types";
import { useNodeDensity } from "@/lib/node-density-context";

type ContainmentItem = {
  id: string;
  name: string;
  type: string;
  color: string;
};

// 4방향 핸들 — ConnectionMode.Loose 라 각 핸들이 source/target 양쪽 다 됨.
// id 부여로 연결 시작·도착 위치가 엣지에 기록됨 (page.tsx 가 metadata 로 영속).
function NodeHandles({ color, visible }: { color: string; visible: boolean }) {
  const cls = [
    "!h-2 !w-2 !border-0 transition-opacity",
    visible ? "opacity-100" : "opacity-0",
  ].join(" ");
  const bg: CSSProperties = {
    background: color,
    pointerEvents: visible ? "auto" : "none",
  };
  return (
    <>
      <Handle type="target" position={Position.Top} id="t" className={cls} style={bg} />
      <Handle type="source" position={Position.Bottom} id="b" className={cls} style={bg} />
      <Handle type="target" position={Position.Left} id="l" className={cls} style={bg} />
      <Handle type="source" position={Position.Right} id="r" className={cls} style={bg} />
    </>
  );
}

// 그룹 소속 배지 — 노드 좌상단에 부모 그룹 목록(Subnet > VPC) 표시.
// page.tsx 가 기하적 포함 판정으로 data.containment 를 주입.
function ContainmentBadge({
  containment,
  visible,
}: {
  containment: ContainmentItem[];
  visible: boolean;
}) {
  if (!visible || containment.length === 0) return null;
  const label = containment.map((item) => item.name).join(" > ");
  const nearest = containment[0];
  return (
    <div
      className="pointer-events-none absolute -top-2.5 left-1 z-10 max-w-[90%] truncate rounded-sm px-1 py-px text-[9px] font-bold leading-none text-white"
      style={{ background: nearest.color }}
      title={`${label} 에 속함`}
    >
      ⊂ {label}
    </div>
  );
}

export function AwsNode({ data, type, selected }: NodeProps) {
  const def = getNodeTypeDef(type as string);
  const color = def?.color || "var(--color-text-muted)";
  const displayName =
    (data?.display_name as string) || def?.displayName || (type as string);
  const { density } = useNodeDensity();
  const containment = (data?.containment as ContainmentItem[] | undefined) || [];
  const validationIssues =
    (data?.validationIssues as { message: string; suggested_action?: string | null }[] | undefined) || [];
  const hasValidationError = validationIssues.length > 0;
  const validationTitle = validationIssues
    .map((issue) => issue.suggested_action || issue.message)
    .join("\n");
  const showContainmentBadge = Boolean(data?.showContainmentBadge);

  const isCompact = density === "compact";
  const minWidth = isCompact ? 72 : 180;
  const minHeight = isCompact ? 68 : 56;

  if (isCompact) {
    // 컴팩트 = 흰 배경/테두리/그림자 없음. 아이콘 + englishName(줄임말) 만.
    // selected 시 outline 으로만 표시.
    return (
      <div
        className={[
          "relative flex h-full w-full flex-col items-center justify-center gap-1 transition-all",
          selected || hasValidationError ? "outline outline-2 outline-offset-2 rounded-sm" : "",
        ].join(" ")}
        style={{
          minWidth,
          minHeight,
          outlineColor: hasValidationError
            ? "var(--color-danger)"
            : selected
              ? "var(--color-accent)"
              : undefined,
        }}
        title={hasValidationError ? validationTitle : undefined}
      >
        <ContainmentBadge
          containment={containment}
          visible={showContainmentBadge}
        />
        <NodeResizer
          isVisible={selected}
          minWidth={minWidth}
          minHeight={minHeight}
          color={color}
          handleStyle={{
            width: 8,
            height: 8,
            borderRadius: 2,
            background: "#fff",
            border: `2px solid ${color}`,
            pointerEvents: "auto",
          }}
          lineStyle={{ borderColor: color, borderWidth: 1, pointerEvents: "auto" }}
        />
        {def?.iconFile ? (
          <img
            src={`/icons/aws/${def.iconFile}`}
            alt={def.englishName}
            width={40}
            height={40}
          />
        ) : (
          <div
            className="h-4 w-4 shrink-0 rounded-full"
            style={{ background: color }}
          />
        )}
        <div
          className="max-w-full text-center text-xs font-bold uppercase leading-tight"
          style={{ color }}
        >
          {def?.englishName || (type as string)}
        </div>
        <NodeHandles color={color} visible={selected} />
        {hasValidationError && (
          <div className="absolute -right-2 -top-2 rounded-full bg-[var(--color-danger)] px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">
            !
          </div>
        )}
      </div>
    );
  }

  // standard (기본)
  return (
    <div
      className={[
        "relative flex h-full w-full items-center gap-3 rounded-md border bg-[var(--color-surface)] px-3 py-2 transition-all",
        hasValidationError
          ? "border-[var(--color-danger)] shadow-[0_0_0_2px_color-mix(in_srgb,var(--color-danger)_24%,transparent)]"
          : selected
          ? "border-[var(--color-accent)] shadow-[var(--shadow-md)] ring-2 ring-[var(--color-accent)]/30"
          : "border-transparent shadow-none hover:bg-[var(--color-bg-subtle)]",
      ].join(" ")}
      style={{ minWidth, minHeight }}
      title={hasValidationError ? validationTitle : undefined}
    >
      <ContainmentBadge
        containment={containment}
        visible={showContainmentBadge}
      />
      <NodeResizer
        isVisible={selected}
        minWidth={minWidth}
        minHeight={minHeight}
        color={color}
        handleStyle={{
          width: 8,
          height: 8,
          borderRadius: 2,
          background: "#fff",
          border: `2px solid ${color}`,
          pointerEvents: "auto",
        }}
        lineStyle={{ borderColor: color, borderWidth: 1, pointerEvents: "auto" }}
      />
      {hasValidationError && (
        <div className="absolute -right-2 -top-2 rounded-full bg-[var(--color-danger)] px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">
          !
        </div>
      )}
      {def?.iconFile ? (
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md"
          style={{ background: `${color}14` }}
        >
          <img
            src={`/icons/aws/${def.iconFile}`}
            alt={def.englishName}
            width={28}
            height={28}
          />
        </div>
      ) : (
        <div
          className="h-2 w-2 shrink-0 rounded-full"
          style={{ background: color }}
        />
      )}
      <div className="min-w-0">
        <div
          className="text-xs font-semibold uppercase"
          style={{ color }}
        >
          {def?.englishName || (type as string)}
        </div>
        <div className="mt-0.5 text-sm font-semibold text-[var(--color-text)]">
          {displayName}
        </div>
      </div>
      <NodeHandles color={color} visible={selected} />
    </div>
  );
}

export const nodeTypes = ALL_NODE_TYPES.reduce<Record<string, typeof AwsNode>>(
  (acc, def) => {
    acc[def.type] = AwsNode;
    return acc;
  },
  {},
);
