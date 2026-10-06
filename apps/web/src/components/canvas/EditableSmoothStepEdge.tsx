"use client";

import {
  BaseEdge,
  getSmoothStepPath,
  useReactFlow,
  type EdgeProps,
} from "@xyflow/react";
import { useCallback } from "react";

type EditableEdgeData = {
  pathStepPosition?: number;
  onStepPositionChange?: (edgeId: string, stepPosition: number) => void;
};

function clampStep(value: number): number {
  return Math.min(0.9, Math.max(0.1, value));
}

export function EditableSmoothStepEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  style,
  markerStart,
  markerEnd,
  data,
  interactionWidth,
}: EdgeProps) {
  const edgeData = (data || {}) as EditableEdgeData;
  const stepPosition =
    typeof edgeData.pathStepPosition === "number"
      ? edgeData.pathStepPosition
      : 0.5;
  const { screenToFlowPosition } = useReactFlow();
  const [path, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 12,
    stepPosition,
  });

  const onBendPointerDown = useCallback(
    (event: React.PointerEvent<SVGCircleElement>) => {
      event.preventDefault();
      event.stopPropagation();
      const pointerId = event.pointerId;
      event.currentTarget.setPointerCapture(pointerId);

      const update = (clientX: number, clientY: number) => {
        const point = screenToFlowPosition({ x: clientX, y: clientY });
        const horizontal = Math.abs(targetX - sourceX) >= Math.abs(targetY - sourceY);
        const raw = horizontal
          ? (point.x - sourceX) / (targetX - sourceX || 1)
          : (point.y - sourceY) / (targetY - sourceY || 1);
        edgeData.onStepPositionChange?.(id, clampStep(raw));
      };

      const handleMove = (moveEvent: PointerEvent) => {
        update(moveEvent.clientX, moveEvent.clientY);
      };
      const handleUp = () => {
        window.removeEventListener("pointermove", handleMove);
        window.removeEventListener("pointerup", handleUp);
      };

      window.addEventListener("pointermove", handleMove);
      window.addEventListener("pointerup", handleUp, { once: true });
      update(event.clientX, event.clientY);
    },
    [edgeData, id, screenToFlowPosition, sourceX, sourceY, targetX, targetY],
  );

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        labelX={labelX}
        labelY={labelY}
        style={style}
        markerStart={markerStart}
        markerEnd={markerEnd}
        interactionWidth={interactionWidth ?? 24}
      />
      {selected && (
        <>
          <circle
            className="eolgae-edge-end-handle"
            cx={sourceX}
            cy={sourceY}
            r={5}
          />
          <circle
            className="eolgae-edge-end-handle"
            cx={targetX}
            cy={targetY}
            r={5}
          />
          <circle
            className="eolgae-edge-bend-handle"
            cx={labelX}
            cy={labelY}
            r={5}
            onPointerDown={onBendPointerDown}
          />
        </>
      )}
    </>
  );
}
