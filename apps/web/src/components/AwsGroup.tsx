"use client";

import type { CSSProperties } from "react";
import { Handle, NodeResizer, Position, type NodeProps } from "@xyflow/react";
import {
  AWS_GROUP_TYPES,
  getGroupTypeDef,
} from "@/lib/group-types";

// 외곽선 클릭 영역 두께 (PowerPoint/Hancom 의 도형 외곽선 클릭 패턴).
// strip 4개 + 헤더만 pointer-events: auto, 본체는 자식 노드로 통과.
const RING_THICKNESS = 8;

// NodeResizer 최소 크기
const MIN_W = 240;
const MIN_H = 140;

type ContainmentItem = {
  id: string;
  name: string;
  type: string;
  color: string;
};

const MIN_LABEL_PT = 6;
const MAX_LABEL_PT = 18;

function normalizeLabelPt(value: unknown): number {
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
    return Math.min(MAX_LABEL_PT, Math.max(MIN_LABEL_PT, parsed));
  }
  return 9;
}

function labelPtStyle(pt: number): CSSProperties {
  // CSS px conversion follows the standard 1pt = 1.333px.
  const px = pt * 1.333;
  return {
    fontSize: px,
    lineHeight: `${Math.max(12, px * 1.25)}px`,
  };
}

function iconSizeForPt(pt: number): number {
  return Math.min(20, Math.max(12, Math.round(pt * 1.6)));
}

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
      className="pointer-events-none absolute -top-2.5 left-2 z-10 max-w-[75%] truncate rounded-sm px-1 py-px text-[9px] font-bold leading-none text-white"
      style={{ background: nearest.color }}
      title={`${label} 에 속함`}
    >
      ⊂ {label}
    </div>
  );
}

function GroupHandles({
  color,
  visible,
}: {
  color: string;
  visible: boolean;
}) {
  const cls = [
    "!h-2 !w-2 !border-0 transition-opacity",
    visible ? "opacity-100" : "opacity-0",
  ].join(" ");
  const style: CSSProperties = {
    background: color,
    pointerEvents: visible ? "auto" : "none",
  };

  return (
    <>
      <Handle type="target" position={Position.Top} id="t" className={cls} style={style} />
      <Handle type="source" position={Position.Bottom} id="b" className={cls} style={style} />
      <Handle type="target" position={Position.Left} id="l" className={cls} style={style} />
      <Handle type="source" position={Position.Right} id="r" className={cls} style={style} />
    </>
  );
}

export function AwsGroup({ data, type, selected }: NodeProps) {
  const def = getGroupTypeDef(type as string);
  if (!def) return null;

  const displayName = (data?.display_name as string) || def.displayName;
  const props = (data?.properties as Record<string, unknown>) || {};
  const cidr = (props.cidr as string) || "";
  const az = (props.availability_zone as string) || "";
  const subnetType = (props.type as string) || "";
  const groupLabelPt = normalizeLabelPt(data?.groupLabelSize);
  const showCidr = data?.showCidr !== false;
  const showAz = data?.showAz !== false;
  const containment = (data?.containment as ContainmentItem[] | undefined) || [];
  const validationIssues =
    (data?.validationIssues as { message: string; suggested_action?: string | null }[] | undefined) || [];
  const hasValidationError = validationIssues.length > 0;
  const validationTitle = validationIssues
    .map((issue) => issue.suggested_action || issue.message)
    .join("\n");
  const showContainmentBadge = Boolean(data?.showContainmentBadge);
  const detailParts = [
    showCidr && cidr ? cidr : null,
    showAz && az ? az : null,
    subnetType ? `(${subnetType})` : null,
  ].filter(Boolean);
  const labelStyle = labelPtStyle(groupLabelPt);
  const iconSize = iconSizeForPt(groupLabelPt);

  return (
    // width/height 는 ReactFlow node.width/height 가 결정 (NodeResizer 가 변경).
    // root 는 본체 통과 (자식 노드 클릭/연결 안 가로채게).
    <div
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        pointerEvents: "none",
      }}
      title={hasValidationError ? validationTitle : undefined}
    >
      <ContainmentBadge
        containment={containment}
        visible={showContainmentBadge}
      />
      {/* 1. 시각 fill + border (pointer 무관) */}
      <div
        className={[
          "rounded-md border-2 border-dashed transition-all",
          selected ? "ring-2 ring-[var(--color-accent)]/40" : "",
          hasValidationError ? "ring-2 ring-[var(--color-danger)]/60" : "",
        ].join(" ")}
        style={{
          position: "absolute",
          inset: 0,
          background: def.fillColor,
          borderColor: hasValidationError
            ? "var(--color-danger)"
            : selected
              ? def.borderColor
              : "transparent",
          pointerEvents: "none",
        }}
      />

      {/* 2. NodeResizer — selected 시 모서리/변에 작은 네모 핸들 표시.
            wrapper pointer-events:none 일 때도 핸들만 잡히도록 명시 auto. */}
      <NodeResizer
        isVisible={selected}
        minWidth={MIN_W}
        minHeight={MIN_H}
        color={def.borderColor}
        handleStyle={{
          width: 10,
          height: 10,
          borderRadius: 2,
          background: "#fff",
          border: `2px solid ${def.borderColor}`,
          pointerEvents: "auto",
        }}
        lineStyle={{
          borderColor: def.borderColor,
          borderWidth: 1,
          pointerEvents: "auto",
        }}
      />

      {/* 3. 외곽선 클릭 영역 (4 strip) — group 선택 + 이동.
            본체 클릭은 자식 노드로 통과. */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: RING_THICKNESS,
          pointerEvents: "auto",
          cursor: "move",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: RING_THICKNESS,
          pointerEvents: "auto",
          cursor: "move",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 0,
          width: RING_THICKNESS,
          pointerEvents: "auto",
          cursor: "move",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          right: 0,
          width: RING_THICKNESS,
          pointerEvents: "auto",
          cursor: "move",
        }}
      />

      {/* 4. 헤더 — top strip 위에 덮여 우선 클릭. Handle + 라벨. */}
      <div
        className="flex items-center justify-between gap-2 overflow-hidden border-b-2 border-dashed px-3 py-1.5"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          borderColor: selected ? def.borderColor : "transparent",
          background: def.fillColor,
          borderRadius: "6px 6px 0 0",
          pointerEvents: "auto",
          cursor: "move",
        }}
      >
        {hasValidationError && (
          <div className="absolute -right-2 -top-2 rounded-full bg-[var(--color-danger)] px-1.5 py-0.5 text-[9px] font-bold leading-none text-white">
            !
          </div>
        )}
        <GroupHandles color={def.borderColor} visible={selected} />
        <span
          className="flex min-w-0 items-center gap-1.5 font-bold uppercase"
          style={{ color: def.borderColor, ...labelStyle }}
        >
          {def.iconFile ? (
            <img
              src={`/icons/aws/${def.iconFile}`}
              alt={def.englishName}
              width={iconSize}
              height={iconSize}
              className="shrink-0"
            />
          ) : null}
          <span className="shrink-0">{def.englishName}</span>
          <span className="truncate font-semibold normal-case">
            {displayName}
          </span>
        </span>
        {detailParts.length > 0 && (
          <span
            className="shrink-0 whitespace-nowrap font-medium"
            style={{ color: `${def.borderColor}cc`, ...labelStyle }}
          >
            {detailParts.join(" / ")}
          </span>
        )}
      </div>
    </div>
  );
}

export const groupNodeTypes = AWS_GROUP_TYPES.reduce<
  Record<string, typeof AwsGroup>
>((acc, def) => {
  acc[def.type] = AwsGroup;
  return acc;
}, {});
