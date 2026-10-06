import { useCallback, useState } from "react";

import {
  approvePlanDeployment,
  getPlanDeployment,
  startApplyDeployment,
  startDestroyDeployment,
  startDestroyPlan,
  startTofuPlan,
  type PlanDeployment,
  type TofuPlanResult,
} from "@/lib/api";

type UsePlanRunnerArgs = {
  canvasId?: string;
  onBeforeRun?: () => void;
  onError: (message: string) => void;
};

export function usePlanRunner({
  canvasId,
  onBeforeRun,
  onError,
}: UsePlanRunnerArgs) {
  const [planning, setPlanning] = useState(false);
  const [applying, setApplying] = useState(false);
  const [destroying, setDestroying] = useState(false);
  const [tofuPlan, setTofuPlan] = useState<TofuPlanResult | null>(null);
  const [planDeployment, setPlanDeployment] = useState<PlanDeployment | null>(null);

  const runPlan = useCallback(async () => {
    if (!canvasId) return;
    setPlanning(true);
    setTofuPlan(null);
    setPlanDeployment(null);
    onBeforeRun?.();
    try {
      const deployment = await startTofuPlan(canvasId);
      setPlanDeployment(deployment);

      for (let attempt = 0; attempt < 180; attempt += 1) {
        const current =
          attempt === 0
            ? deployment
            : await getPlanDeployment(canvasId, deployment.id);
        setPlanDeployment(current);

        if (current.status === "success" && current.plan_result) {
          setTofuPlan({
            ...current.plan_result,
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        if (current.status === "failed") {
          setTofuPlan({
            ...(current.plan_result || {
              ok: false,
              steps: [],
              work_dir: "",
              plan_text: null,
            }),
            ok: false,
            error:
              current.error_message ||
              current.plan_result?.error ||
              "비동기 Plan 실패",
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, 2000));
      }

      throw new Error("Plan 실행이 6분 안에 완료되지 않음");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setPlanning(false);
    }
  }, [canvasId, onBeforeRun, onError]);

  const approveAndApply = useCallback(async () => {
    if (!canvasId || !planDeployment?.id) return;
    setApplying(true);
    try {
      const approved =
        planDeployment.status === "approved"
          ? planDeployment
          : await approvePlanDeployment(canvasId, planDeployment.id);
      setPlanDeployment(approved);
      const applyDeployment = await startApplyDeployment(canvasId, approved.id);
      setPlanDeployment(applyDeployment);

      for (let attempt = 0; attempt < 240; attempt += 1) {
        const current =
          attempt === 0
            ? applyDeployment
            : await getPlanDeployment(canvasId, applyDeployment.id);
        setPlanDeployment(current);

        if ((current.status === "applied" || current.status === "failed") && current.plan_result) {
          setTofuPlan({
            ...current.plan_result,
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        if (current.status === "failed") {
          setTofuPlan({
            ok: false,
            steps: [],
            work_dir: "",
            plan_text: null,
            error: current.error_message || "Apply 실패",
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, 2000));
      }

      throw new Error("Apply 실행이 8분 안에 완료되지 않음");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setApplying(false);
    }
  }, [canvasId, onError, planDeployment]);

  const runDestroyPlan = useCallback(async () => {
    if (!canvasId) return;
    setPlanning(true);
    setTofuPlan(null);
    setPlanDeployment(null);
    onBeforeRun?.();
    try {
      const deployment = await startDestroyPlan(canvasId);
      setPlanDeployment(deployment);

      for (let attempt = 0; attempt < 180; attempt += 1) {
        const current =
          attempt === 0
            ? deployment
            : await getPlanDeployment(canvasId, deployment.id);
        setPlanDeployment(current);

        if (current.status === "success" && current.plan_result) {
          setTofuPlan({
            ...current.plan_result,
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        if (current.status === "failed") {
          setTofuPlan({
            ...(current.plan_result || {
              ok: false,
              steps: [],
              work_dir: "",
              plan_text: null,
            }),
            ok: false,
            error:
              current.error_message ||
              current.plan_result?.error ||
              "Destroy Plan 실패",
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, 2000));
      }

      throw new Error("Destroy Plan 실행이 6분 안에 완료되지 않음");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setPlanning(false);
    }
  }, [canvasId, onBeforeRun, onError]);

  const approveAndDestroy = useCallback(async () => {
    if (!canvasId || !planDeployment?.id) return;
    setDestroying(true);
    try {
      const approved =
        planDeployment.status === "approved"
          ? planDeployment
          : await approvePlanDeployment(canvasId, planDeployment.id);
      setPlanDeployment(approved);
      const destroyDeployment = await startDestroyDeployment(canvasId, approved.id);
      setPlanDeployment(destroyDeployment);

      for (let attempt = 0; attempt < 240; attempt += 1) {
        const current =
          attempt === 0
            ? destroyDeployment
            : await getPlanDeployment(canvasId, destroyDeployment.id);
        setPlanDeployment(current);

        if ((current.status === "destroyed" || current.status === "failed") && current.plan_result) {
          setTofuPlan({
            ...current.plan_result,
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        if (current.status === "failed") {
          setTofuPlan({
            ok: false,
            steps: [],
            work_dir: "",
            plan_text: null,
            error: current.error_message || "Destroy 실패",
            deployment_id: current.id,
            deployment_status: current.status,
            assumed_arn: current.assumed_arn,
          });
          return;
        }

        await new Promise((resolve) => setTimeout(resolve, 2000));
      }

      throw new Error("Destroy 실행이 8분 안에 완료되지 않음");
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setDestroying(false);
    }
  }, [canvasId, onError, planDeployment]);

  return {
    planning,
    applying,
    destroying,
    tofuPlan,
    setTofuPlan,
    planDeployment,
    setPlanDeployment,
    runPlan,
    approveAndApply,
    runDestroyPlan,
    approveAndDestroy,
  };
}
