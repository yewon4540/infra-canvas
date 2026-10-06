// Eolgae shared types.
// 최종 타입은 FastAPI OpenAPI schema → openapi-typescript codegen 으로 생성 예정.
// 상세 schema: docs/ARCHITECTURE.md

export type CanvasState = "design" | "deploy" | "running";

export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

// Placeholder — Canvas / Node / Edge / Group 전체 타입은 OpenAPI codegen 후 대체
