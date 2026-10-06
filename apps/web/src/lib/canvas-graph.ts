import { type Node } from "@xyflow/react";

import { getGroupTypeDef } from "@/lib/group-types";

export const SNAP_GRID: [number, number] = [20, 20];

const ALIGN_THRESHOLD = 10;

export type AlignmentGuides = {
  x?: number;
  y?: number;
};

export type ContainmentItem = {
  id: string;
  name: string;
  type: string;
  color: string;
};

type NodeRect = {
  left: number;
  centerX: number;
  right: number;
  top: number;
  centerY: number;
  bottom: number;
};

type GroupBox = ContainmentItem & {
  x: number;
  y: number;
  w: number;
  h: number;
  area: number;
};

export function snapPosition(position: { x: number; y: number }) {
  return {
    x: Math.round(position.x / SNAP_GRID[0]) * SNAP_GRID[0],
    y: Math.round(position.y / SNAP_GRID[1]) * SNAP_GRID[1],
  };
}

export function findMagneticAlignment(
  dragging: Node,
  candidates: Node[],
): { position: { x: number; y: number }; guides: AlignmentGuides } {
  const draggingRect = getNodeRect(dragging);
  const xPoints = [
    { value: draggingRect.left },
    { value: draggingRect.centerX },
    { value: draggingRect.right },
  ];
  const yPoints = [
    { value: draggingRect.top },
    { value: draggingRect.centerY },
    { value: draggingRect.bottom },
  ];

  let bestX: { delta: number; guide: number } | null = null;
  let bestY: { delta: number; guide: number } | null = null;

  for (const node of candidates) {
    if (node.id === dragging.id) continue;
    const rect = getNodeRect(node);
    const candidateXs = [rect.left, rect.centerX, rect.right];
    const candidateYs = [rect.top, rect.centerY, rect.bottom];

    for (const point of xPoints) {
      for (const candidate of candidateXs) {
        const delta = candidate - point.value;
        if (
          Math.abs(delta) <= ALIGN_THRESHOLD &&
          (!bestX || Math.abs(delta) < Math.abs(bestX.delta))
        ) {
          bestX = { delta, guide: candidate };
        }
      }
    }

    for (const point of yPoints) {
      for (const candidate of candidateYs) {
        const delta = candidate - point.value;
        if (
          Math.abs(delta) <= ALIGN_THRESHOLD &&
          (!bestY || Math.abs(delta) < Math.abs(bestY.delta))
        ) {
          bestY = { delta, guide: candidate };
        }
      }
    }
  }

  return {
    position: {
      x: dragging.position.x + (bestX?.delta ?? 0),
      y: dragging.position.y + (bestY?.delta ?? 0),
    },
    guides: {
      ...(bestX ? { x: bestX.guide } : {}),
      ...(bestY ? { y: bestY.guide } : {}),
    },
  };
}

export function assignParentGroups(nodes: Node[]): Node[] {
  const groupBoxes = buildGroupBoxes(nodes);
  return nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      parent_group_id: findDirectParentId(node, groupBoxes),
    },
  }));
}

export function getContainment(
  node: Node,
  nodeById: Map<string, Node>,
): ContainmentItem[] {
  const result: ContainmentItem[] = [];
  const seen = new Set<string>();
  let parentId =
    (node.data?.parent_group_id as string | null | undefined) ?? null;

  while (parentId && !seen.has(parentId)) {
    seen.add(parentId);
    const parent = nodeById.get(parentId);
    if (!parent) break;
    const def = getGroupTypeDef(parent.type || "");
    result.push({
      id: parent.id,
      name: (parent.data?.display_name as string) || def?.englishName || "",
      type: parent.type || "",
      color: def?.borderColor || "#888",
    });
    parentId =
      (parent.data?.parent_group_id as string | null | undefined) ?? null;
  }

  return result;
}

export function getDescendantIds(nodes: Node[], parentId: string): Set<string> {
  const childrenByParent = new Map<string, string[]>();
  for (const node of nodes) {
    const nodeParent =
      (node.data?.parent_group_id as string | null | undefined) ?? null;
    if (!nodeParent) continue;
    childrenByParent.set(nodeParent, [
      ...(childrenByParent.get(nodeParent) || []),
      node.id,
    ]);
  }

  const descendants = new Set<string>();
  const stack = [...(childrenByParent.get(parentId) || [])];
  while (stack.length > 0) {
    const childId = stack.pop()!;
    if (descendants.has(childId)) continue;
    descendants.add(childId);
    stack.push(...(childrenByParent.get(childId) || []));
  }
  return descendants;
}

export function getAlignmentCandidates(node: Node, nodes: Node[]): Node[] {
  if (!getGroupTypeDef(node.type || "")) return nodes;
  const descendants = getDescendantIds(nodes, node.id);
  return nodes.filter((candidate) => !descendants.has(candidate.id));
}

function getNodeSize(node: Node): { width: number; height: number } {
  const groupDef = getGroupTypeDef(node.type || "");
  return {
    width:
      (node.width as number | undefined) ??
      groupDef?.defaultSize.width ??
      160,
    height:
      (node.height as number | undefined) ??
      groupDef?.defaultSize.height ??
      60,
  };
}

function getNodeRect(node: Node): NodeRect {
  const { width, height } = getNodeSize(node);
  return {
    left: node.position.x,
    centerX: node.position.x + width / 2,
    right: node.position.x + width,
    top: node.position.y,
    centerY: node.position.y + height / 2,
    bottom: node.position.y + height,
  };
}

function getNodeArea(node: Node): number {
  const { width, height } = getNodeSize(node);
  return width * height;
}

function findDirectParentId(node: Node, groupBoxes: GroupBox[]): string | null {
  const rect = getNodeRect(node);
  const cx = rect.centerX;
  const cy = rect.centerY;
  const nodeType = node.type || "";
  const isGroup = Boolean(getGroupTypeDef(nodeType));
  const nodeArea = getNodeArea(node);

  const parent = groupBoxes
    .filter(
      (group) =>
        group.id !== node.id &&
        (!isGroup || group.area > nodeArea) &&
        isValidParentGroup(nodeType, group.type) &&
        cx >= group.x &&
        cx <= group.x + group.w &&
        cy >= group.y &&
        cy <= group.y + group.h,
    )
    .sort((a, b) => a.area - b.area)[0];

  return parent?.id ?? null;
}

function isValidParentGroup(childType: string, parentType: string): boolean {
  if (childType === "aws.ec2.vpc") return false;
  if (childType === "aws.ec2.subnet") return parentType === "aws.ec2.vpc";
  if (getGroupTypeDef(childType)) return false;
  return parentType === "aws.ec2.subnet" || parentType === "aws.ec2.vpc";
}

function buildGroupBoxes(nodes: Node[]): GroupBox[] {
  return nodes
    .filter((n) => getGroupTypeDef(n.type || ""))
    .map((g) => {
      const def = getGroupTypeDef(g.type || "");
      const size = getNodeSize(g);
      return {
        id: g.id,
        name: (g.data?.display_name as string) || def?.englishName || "",
        type: g.type || "",
        color: def?.borderColor || "#888",
        x: g.position.x,
        y: g.position.y,
        w: size.width,
        h: size.height,
        area: size.width * size.height,
      };
    });
}
