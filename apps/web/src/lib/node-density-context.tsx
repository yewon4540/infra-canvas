"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

/**
 * 노드 표기 밀도 — 전역 토글.
 *
 * - `standard`: 아이콘 + 영문 라벨 + 한글 이름, 가로 배치 (기본, 정보 풍부)
 * - `compact`: 아이콘 + 아이콘 아래 한글 이름, 세로 배치 (정보 밀집)
 *
 * localStorage 키 `eolgae-node-density`. 새로고침 후 유지.
 */
export type NodeDensity = "standard" | "compact";

const STORAGE_KEY = "eolgae-node-density";

interface NodeDensityValue {
  density: NodeDensity;
  setDensity: (d: NodeDensity) => void;
}

const NodeDensityContext = createContext<NodeDensityValue>({
  density: "standard",
  setDensity: () => {},
});

export function NodeDensityProvider({ children }: { children: ReactNode }) {
  const [density, setDensityState] = useState<NodeDensity>("standard");

  // localStorage 에서 초기 로드 (SSR 후 client mount 시점)
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "standard" || stored === "compact") {
      setDensityState(stored);
    }
  }, []);

  const setDensity = useCallback((d: NodeDensity) => {
    setDensityState(d);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, d);
    }
  }, []);

  return (
    <NodeDensityContext.Provider value={{ density, setDensity }}>
      {children}
    </NodeDensityContext.Provider>
  );
}

export function useNodeDensity(): NodeDensityValue {
  return useContext(NodeDensityContext);
}
