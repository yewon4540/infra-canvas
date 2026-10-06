// Edge 타입 정의 (CANVAS-SCHEMA.md §Edge 따름).
// 5종: network / depends_on / data_flow / route / reference

export type EdgeKind =
  | "network"
  | "depends_on"
  | "data_flow"
  | "route"
  | "reference";

export interface EdgeTypeDef {
  type: EdgeKind;
  displayName: string;
  description: string;
  color: string;
  strokeWidth: number;
  strokeDasharray?: string;
  animated: boolean;
}

export const EDGE_TYPES: EdgeTypeDef[] = [
  {
    type: "network",
    displayName: "네트워크",
    description: "네트워크 트래픽 (ALB → EC2 등)",
    color: "#3b48cc",
    strokeWidth: 2,
    animated: false,
  },
  {
    type: "depends_on",
    displayName: "의존",
    description: "일반 의존성 (App → DB 등)",
    color: "#94a3b8",
    strokeWidth: 1.75,
    strokeDasharray: "6 4",
    animated: false,
  },
  {
    type: "data_flow",
    displayName: "데이터 흐름",
    description: "데이터 이동 (App → S3 등)",
    color: "#10b981",
    strokeWidth: 2.25,
    animated: true,
  },
  {
    type: "route",
    displayName: "라우팅",
    description: "라우팅 경로 (Subnet → RT → IGW)",
    color: "#a855f7",
    strokeWidth: 2,
    strokeDasharray: "8 3",
    animated: false,
  },
  {
    type: "reference",
    displayName: "참조",
    description: "단순 참조 (EC2 → IAM Role 등, 시각적 보조)",
    color: "#cbd5e1",
    strokeWidth: 1.25,
    strokeDasharray: "3 3",
    animated: false,
  },
];

export const DEFAULT_EDGE_KIND: EdgeKind = "network";

export function getEdgeTypeDef(type: string | undefined): EdgeTypeDef {
  return (
    EDGE_TYPES.find((t) => t.type === type) ??
    EDGE_TYPES.find((t) => t.type === DEFAULT_EDGE_KIND)!
  );
}

export function getEdgeStyle(type: string | undefined): React.CSSProperties {
  const def = getEdgeTypeDef(type);
  return {
    stroke: def.color,
    strokeWidth: def.strokeWidth,
    ...(def.strokeDasharray ? { strokeDasharray: def.strokeDasharray } : {}),
  };
}

export function getEdgeAnimated(type: string | undefined): boolean {
  return getEdgeTypeDef(type).animated;
}
