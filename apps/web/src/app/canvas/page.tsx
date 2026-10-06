"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createCanvas,
  createCanvasFromTemplate,
  deleteCanvas,
  duplicateCanvas,
  getDeploymentSummary,
  listAwsConnections,
  listCanvasTemplates,
  listCanvases,
  listEnvironments,
  listGroups,
  listTargets,
  updateCanvas,
  type ApiCanvasGroup,
  type AwsConnection,
  type Canvas,
  type CanvasKind,
  type CanvasState,
  type CanvasTemplate,
  type DeploymentSummary,
  type Environment,
  type Target,
} from "@/lib/api";
import { ConfirmModal } from "@/components/ConfirmModal";
import { WorkspaceHeader, WorkspaceShell } from "@/components/WorkspaceShell";
import { CanvasDashboardView } from "@/components/canvas-hub/CanvasDashboardView";
import {
  CanvasListTable,
  type CanvasFilter,
} from "@/components/canvas-hub/CanvasListTable";
import { CanvasQuickCreatePanel } from "@/components/canvas-hub/CanvasQuickCreatePanel";

type WorkspaceView = "dashboard" | "canvas";

function isAppliedState(state: CanvasState) {
  return state === "applied" || state === "running" || state === "deploy";
}

export default function Home() {
  const router = useRouter();
  const [canvases, setCanvases] = useState<Canvas[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<CanvasTemplate[]>([]);
  const [groups, setGroups] = useState<ApiCanvasGroup[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [awsConnections, setAwsConnections] = useState<AwsConnection[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState("");
  const [selectedAwsConnectionId, setSelectedAwsConnectionId] = useState("");
  const [selectedKubernetesTargetId, setSelectedKubernetesTargetId] = useState("");
  const [kubernetesTargets, setKubernetesTargets] = useState<Target[]>([]);
  const [deploymentSummary, setDeploymentSummary] =
    useState<DeploymentSummary | null>(null);
  const [creatingTemplateId, setCreatingTemplateId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<CanvasFilter>("all");
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>("dashboard");
  const [pendingDelete, setPendingDelete] = useState<Canvas | null>(null);

  useEffect(() => {
    Promise.all([
      listCanvases(),
      listCanvasTemplates(),
      listGroups(),
      listEnvironments(),
      listAwsConnections(),
      listTargets("kubernetes_cluster"),
      getDeploymentSummary(),
    ])
      .then(([
        list,
        templateList,
        groupList,
        environmentList,
        connectionList,
        targetList,
        summary,
      ]) => {
        setCanvases(list);
        setTemplates(templateList);
        setGroups(groupList);
        setEnvironments(environmentList);
        setAwsConnections(connectionList);
        setKubernetesTargets(targetList);
        setDeploymentSummary(summary);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleNewCanvas(canvasKind: Extract<CanvasKind, "aws" | "kubernetes">) {
    setCreating(true);
    setError(null);
    try {
      const canvas = await createCanvas({
        name: canvasKind === "aws" ? "New AWS Canvas" : "New Kubernetes Canvas",
        canvas_kind: canvasKind,
        group_id: selectedGroupId || null,
        environment_id: selectedEnvironmentId || null,
        aws_connection_id: canvasKind === "aws" ? selectedAwsConnectionId || null : null,
        target_id: canvasKind === "kubernetes" ? selectedKubernetesTargetId || null : null,
      });
      router.push(`/canvas/${canvas.id}`);
    } catch (e) {
      setError((e as Error).message);
      setCreating(false);
    }
  }

  async function handleDeleteConfirmed() {
    if (!pendingDelete) return;
    const target = pendingDelete;
    setPendingDelete(null);
    try {
      await deleteCanvas(target.id);
      setCanvases((prev) => prev.filter((c) => c.id !== target.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDuplicate(canvas: Canvas) {
    setDuplicatingId(canvas.id);
    setError(null);
    try {
      const copy = await duplicateCanvas(canvas.id);
      router.push(`/canvas/${copy.id}`);
    } catch (e) {
      setError((e as Error).message);
      setDuplicatingId(null);
    }
  }

  async function handleCreateFromTemplate(template: CanvasTemplate) {
    setCreatingTemplateId(template.id);
    setError(null);
    try {
      const canvas = await createCanvasFromTemplate({
        template_id: template.id,
        name: template.name,
        group_id: selectedGroupId || null,
        environment_id: selectedEnvironmentId || null,
        aws_connection_id: selectedAwsConnectionId || null,
      });
      router.push(`/canvas/${canvas.id}`);
    } catch (e) {
      setError((e as Error).message);
      setCreatingTemplateId(null);
    }
  }

  async function handleRename(id: string, currentName: string) {
    const input = window.prompt("새 이름:", currentName);
    if (input === null) return;
    const trimmed = input.trim();
    if (!trimmed || trimmed === currentName) return;
    try {
      const updated = await updateCanvas(id, { name: trimmed });
      setCanvases((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const counts: Record<CanvasFilter, number> = {
    all: canvases.length,
    design: canvases.filter((c) => c.state === "design").length,
    applied: canvases.filter((c) => isAppliedState(c.state)).length,
    destroyed: canvases.filter((c) => c.state === "destroyed").length,
  };

  const filtered =
    filter === "all"
      ? canvases
      : filter === "applied"
        ? canvases.filter((c) => isAppliedState(c.state))
        : canvases.filter((c) => c.state === filter);
  const groupById = new Map(groups.map((group) => [group.id, group]));
  const environmentById = new Map(
    environments.map((environment) => [environment.id, environment]),
  );
  const awsConnectionById = new Map(
    awsConnections.map((connection) => [connection.id, connection]),
  );
  const selectedGroup = selectedGroupId ? groupById.get(selectedGroupId) : null;
  const selectedEnvironment = selectedEnvironmentId
    ? environmentById.get(selectedEnvironmentId)
    : null;
  const kubernetesTargetById = new Map(
    kubernetesTargets.map((target) => [target.id, target]),
  );
  const sharedContextSummary =
    [selectedGroup?.name, selectedEnvironment?.slug].filter(Boolean).join(" / ") ||
    "Group / Environment 미지정";
  const hasSharedContext =
    Boolean(selectedGroupId) ||
    Boolean(selectedEnvironmentId);
  return (
    <WorkspaceShell
      active={workspaceView}
      onSectionChange={(section) => {
        if (section === "settings") return;
        setWorkspaceView(section);
      }}
    >
      {workspaceView === "dashboard" ? (
        <CanvasDashboardView
          canvases={canvases}
          applyCount={counts.applied}
          destroyCount={counts.destroyed}
          designCount={counts.design}
          awsConnectionCount={awsConnections.length}
          kubernetesTargetCount={kubernetesTargets.length}
          environmentCount={environments.length}
          deploymentSummary={deploymentSummary}
        />
      ) : (
        <>
          <WorkspaceHeader
            title="Canvas"
            description="설계 컨텍스트와 캔버스 목록을 관리합니다."
          />
          <CanvasQuickCreatePanel
            loading={loading}
            creating={creating}
            templates={templates}
            creatingTemplateId={creatingTemplateId}
            groups={groups}
            environments={environments}
            awsConnections={awsConnections}
            kubernetesTargets={kubernetesTargets}
            selectedGroupId={selectedGroupId}
            selectedEnvironmentId={selectedEnvironmentId}
            selectedAwsConnectionId={selectedAwsConnectionId}
            selectedKubernetesTargetId={selectedKubernetesTargetId}
            sharedContextSummary={sharedContextSummary}
            hasSharedContext={hasSharedContext}
            onGroupChange={setSelectedGroupId}
            onEnvironmentChange={setSelectedEnvironmentId}
            onAwsConnectionChange={setSelectedAwsConnectionId}
            onKubernetesTargetChange={setSelectedKubernetesTargetId}
            onCreateCanvas={handleNewCanvas}
            onCreateFromTemplate={handleCreateFromTemplate}
          />

      {error && (
        <p className="mb-4 text-sm text-[var(--color-danger)]">오류: {error}</p>
      )}

      <CanvasListTable
        filteredCanvases={filtered}
        loading={loading}
        filter={filter}
        counts={counts}
        groups={groupById}
        environments={environmentById}
        awsConnections={awsConnectionById}
        kubernetesTargets={kubernetesTargetById}
        duplicatingId={duplicatingId}
        onFilterChange={setFilter}
        onRename={handleRename}
        onDuplicate={handleDuplicate}
        onDelete={setPendingDelete}
      />

      {pendingDelete && (
        <ConfirmModal
          title="캔버스 삭제"
          message={
            <>
              <strong>‘{pendingDelete.name}’</strong> 을(를) 삭제합니다.<br />
              휴지통으로 이동하며, 휴지통에서 복구 또는 영구 삭제할 수 있습니다.
            </>
          }
          confirmLabel="휴지통으로 이동"
          cancelLabel="취소"
          danger
          onConfirm={handleDeleteConfirmed}
          onCancel={() => setPendingDelete(null)}
        />
      )}
        </>
      )}
    </WorkspaceShell>
  );
}
