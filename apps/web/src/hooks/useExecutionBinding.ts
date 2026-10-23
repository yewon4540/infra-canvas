import { useEffect, useState } from "react";
import { getExecutionBinding, type ExecutionBinding } from "@/lib/execution-api";

export function useExecutionBinding(canvasId?: string) {
  const [state, setState] = useState<{ id?: string; binding: ExecutionBinding | null; error: string | null }>({
    binding: null, error: null,
  });
  useEffect(() => {
    let active = true;
    if (canvasId) {
      getExecutionBinding(canvasId)
        .then((binding) => { if (active) setState({ id: canvasId, binding, error: null }); })
        .catch((error: Error) => { if (active) setState({ id: canvasId, binding: null, error: error.message }); });
    }
    return () => { active = false; };
  }, [canvasId]);
  const binding = state.id === canvasId ? state.binding : null;
  return {
    allowed: binding?.direct_execution === true,
    message: state.id === canvasId && state.error ? state.error : !binding
      ? "실행 설정 확인 중"
      : binding.backend === "terrakube" ? "Terrakube에서 실행을 관리합니다."
      : binding.direct_execution ? "직접 실행 사용 가능" : "이 설치는 조회·설계 모드입니다.",
  };
}
