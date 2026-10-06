"use client";

import { useEffect, useRef, useState } from "react";
import type {
  FeedbackCategory,
  FeedbackItem,
  FeedbackResponse,
  FeedbackSeverity,
  ReviewContext,
} from "@/lib/api";

interface FeedbackPanelProps {
  feedback: FeedbackResponse | null;
  loading: boolean;
  streamingText: string;
  error: string | null;
  isStale: boolean;
  autoReflect: boolean;
  canStart: boolean;
  heightVh?: number;
  onClose: () => void;
  onStart: (reviewContext?: ReviewContext) => void;
  onStop: () => void;
  onAutoReflectChange: (v: boolean) => void;
  onHeightVhChange?: (height: number) => void;
  onItemClick?: (item: FeedbackItem) => void;
}

const MIN_HEIGHT_VH = 20;
const MAX_HEIGHT_VH = 85;
const DEFAULT_HEIGHT_VH = 40;

const SEVERITY_COLORS: Record<FeedbackSeverity, string> = {
  critical: "var(--color-danger)",
  high: "var(--color-warning)",
  medium: "#ca8a04",
  low: "var(--color-info)",
};

const SEVERITY_LABELS: Record<FeedbackSeverity, string> = {
  critical: "치명",
  high: "높음",
  medium: "보통",
  low: "낮음",
};

const CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  security: "보안",
  cost: "비용",
  ha: "고가용성",
  operations: "운영",
};

// AI 캐릭터 컨셉: 꼼꼼한 컨설턴트
// TODO(BACKLOG): 캐릭터 컨셉 사용자 선택 (시니어 엔지니어 / 친근한 동료 / 꼼꼼한 컨설턴트 등)
const CONSULTANT_VOICE = {
  idle: "검토 준비 완료. [분석 시작]을 눌러주세요. 보안 · 비용 · 고가용성 · 운영 — 네 관점에서 진단합니다.",
  emptyCanvas:
    "캔버스에 컴포넌트를 먼저 배치해주세요. 분석할 대상이 있어야 진단이 가능합니다.",
  staleHeader: "마지막 분석 이후 캔버스가 변경되었습니다.",
  staleBody:
    "변경된 부분은 아직 추적하지 못했습니다. 정확한 진단을 위해 재분석을 권장합니다.",
};

const DEFAULT_REVIEW_CONTEXT: ReviewContext = {
  purpose: "",
  environment: "unknown",
  availability_target: "unknown",
  cost_posture: "unknown",
  traffic_expectation: "unknown",
  notes: "",
};

export function FeedbackPanel({
  feedback,
  loading,
  streamingText,
  error,
  isStale,
  autoReflect,
  canStart,
  heightVh,
  onClose,
  onStart,
  onStop,
  onAutoReflectChange,
  onHeightVhChange,
  onItemClick,
}: FeedbackPanelProps) {
  const showStreaming = loading && !feedback && streamingText.length > 0;
  const [localHeight, setLocalHeight] = useState(DEFAULT_HEIGHT_VH);
  const [reviewContext, setReviewContext] = useState<ReviewContext>(
    DEFAULT_REVIEW_CONTEXT,
  );
  const [contextOpen, setContextOpen] = useState(true);
  const dragStartRef = useRef<{ y: number; height: number } | null>(null);
  const height = heightVh ?? localHeight;
  const setHeight = onHeightVhChange ?? setLocalHeight;

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragStartRef.current) return;
      const deltaPx = dragStartRef.current.y - e.clientY;
      const deltaVh = (deltaPx / window.innerHeight) * 100;
      const next = dragStartRef.current.height + deltaVh;
      setHeight(Math.max(MIN_HEIGHT_VH, Math.min(MAX_HEIGHT_VH, next)));
    };
    const onUp = () => {
      dragStartRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, []);

  const onResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    dragStartRef.current = { y: e.clientY, height };
    document.body.style.cursor = "ns-resize";
    document.body.style.userSelect = "none";
  };

  const showIdle = !loading && !feedback && !error;
  const showStaleBanner = autoReflect && isStale && feedback && !loading;
  const startLabel = feedback ? "재분석" : "분석 시작";
  const handleStart = () => onStart(normalizeReviewContext(reviewContext));

  return (
    <div
      className="absolute inset-x-0 bottom-0 z-[5] flex flex-col border-t border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-lg)]"
      style={{ height: `${height}vh` }}
    >
      <div
        onMouseDown={onResizeStart}
        title="드래그하여 패널 크기 조절"
        className="group h-1.5 shrink-0 cursor-ns-resize border-t-2 border-[var(--color-border)] transition-colors hover:border-[var(--color-accent)]"
      />
      <div className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-4 py-2.5">
        <strong className="text-sm text-[var(--color-text)]">
          AI 피드백
          {feedback ? ` (${feedback.items.length}건)` : null}
          {showStreaming ? ` (스트리밍 ${streamingText.length}자)` : null}
        </strong>
        <button
          onClick={onClose}
          aria-label="닫기"
          className="rounded p-1 text-base leading-none text-[var(--color-text-subtle)] hover:bg-[var(--color-surface)] hover:text-[var(--color-text)]"
        >
          ✕
        </button>
      </div>

      <div className="flex items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2">
        {loading ? (
          <button
            onClick={onStop}
            className="rounded-md border border-[var(--color-warning)] bg-[var(--color-surface)] px-3 py-1 text-xs font-medium text-[var(--color-warning)] hover:bg-[var(--color-warning)]/10"
          >
            ⏸ 중지
          </button>
        ) : (
          <button
            onClick={handleStart}
            disabled={!canStart}
            className={
              canStart
                ? "rounded-md border border-[var(--color-border-strong)] bg-[var(--color-accent)] px-3 py-1 text-xs font-medium text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
                : "cursor-not-allowed rounded-md border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-1 text-xs text-[var(--color-text-subtle)]"
            }
          >
            ▶ {startLabel}
          </button>
        )}
        <label className="ml-2 flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] select-none cursor-pointer">
          <input
            type="checkbox"
            checked={autoReflect}
            onChange={(e) => onAutoReflectChange(e.target.checked)}
            className="h-3.5 w-3.5 cursor-pointer accent-[var(--color-accent)]"
          />
          자동 반영
          <span
            title="캔버스 변경 시 결과를 stale 로 표시"
            className="text-[var(--color-text-subtle)]"
          >
            (?)
          </span>
        </label>
        {isStale && !autoReflect && (
          <span
            className="ml-auto text-xs text-[var(--color-text-subtle)] italic"
            title="자동 반영 꺼짐 — 변경 감지 무시 중"
          >
            (변경 있음)
          </span>
        )}
      </div>

      <ReviewContextEditor
        value={reviewContext}
        open={contextOpen}
        onToggle={() => setContextOpen((v) => !v)}
        onChange={setReviewContext}
      />

      <div className="flex-1 overflow-y-auto">
        {error ? (
          <div className="p-4 text-sm text-[var(--color-danger)]">
            오류: {error}
          </div>
        ) : showStreaming ? (
          <StreamingView text={streamingText} />
        ) : loading ? (
          <div className="p-6 text-center text-sm text-[var(--color-text-muted)]">
            분석 중... (LLM 호출 시작 대기)
          </div>
        ) : showIdle ? (
          <IdleView canStart={canStart} />
        ) : feedback ? (
          <>
            {showStaleBanner && <StaleBanner />}
            <FeedbackView feedback={feedback} onItemClick={onItemClick} />
          </>
        ) : null}
      </div>
    </div>
  );
}

function normalizeReviewContext(value: ReviewContext): ReviewContext | undefined {
  const trimmed: ReviewContext = {
    ...value,
    purpose: value.purpose.trim(),
    notes: value.notes.trim(),
  };
  const hasText = Boolean(trimmed.purpose || trimmed.notes);
  const hasSelection = [
    trimmed.environment,
    trimmed.availability_target,
    trimmed.cost_posture,
    trimmed.traffic_expectation,
  ].some((v) => v !== "unknown");
  return hasText || hasSelection ? trimmed : undefined;
}

function ReviewContextEditor({
  value,
  open,
  onToggle,
  onChange,
}: {
  value: ReviewContext;
  open: boolean;
  onToggle: () => void;
  onChange: (next: ReviewContext) => void;
}) {
  const update = <K extends keyof ReviewContext>(
    key: K,
    next: ReviewContext[K],
  ) => onChange({ ...value, [key]: next });

  return (
    <div className="border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-4 py-2">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left text-xs font-semibold text-[var(--color-text)]"
      >
        <span>검토 기준</span>
        <span className="text-[var(--color-text-subtle)]">
          {open ? "접기" : "펼치기"}
        </span>
      </button>
      {open && (
        <div className="mt-2 grid gap-2">
          <input
            value={value.purpose}
            onChange={(e) => update("purpose", e.target.value)}
            placeholder="예: AWS에 고객센터 채팅 웹 서비스를 만들 거야"
            className="w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-xs text-[var(--color-text)]"
          />
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <ReviewSelect
              label="환경"
              value={value.environment}
              options={[
                ["unknown", "미정"],
                ["dev", "개발"],
                ["staging", "스테이징"],
                ["production", "운영"],
              ]}
              onChange={(v) => update("environment", v)}
            />
            <ReviewSelect
              label="가용성"
              value={value.availability_target}
              options={[
                ["unknown", "미정"],
                ["best_effort", "최소"],
                ["business_hours", "업무시간"],
                ["high_availability", "고가용"],
              ]}
              onChange={(v) => update("availability_target", v)}
            />
            <ReviewSelect
              label="비용"
              value={value.cost_posture}
              options={[
                ["unknown", "미정"],
                ["cheapest", "최저"],
                ["balanced", "균형"],
                ["production_safe", "운영안정"],
              ]}
              onChange={(v) => update("cost_posture", v)}
            />
            <ReviewSelect
              label="트래픽"
              value={value.traffic_expectation}
              options={[
                ["unknown", "미정"],
                ["small", "작음"],
                ["medium", "보통"],
                ["high", "높음"],
              ]}
              onChange={(v) => update("traffic_expectation", v)}
            />
          </div>
          <textarea
            value={value.notes}
            onChange={(e) => update("notes", e.target.value)}
            placeholder="예: 상담원과 고객이 동시에 접속. 첨부파일 가능성 있음."
            rows={2}
            className="w-full resize-none rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5 text-xs text-[var(--color-text)]"
          />
        </div>
      )}
    </div>
  );
}

function ReviewSelect<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (value: T) => void;
}) {
  return (
    <label className="grid gap-1 text-[11px] text-[var(--color-text-muted)]">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="min-w-0 rounded border border-[var(--color-border)] bg-[var(--color-surface)] px-1.5 py-1 text-xs text-[var(--color-text)]"
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function IdleView({ canStart }: { canStart: boolean }) {
  return (
    <div className="p-6 text-center text-sm leading-relaxed text-[var(--color-text-muted)]">
      <p className="mx-auto max-w-md">
        {canStart ? CONSULTANT_VOICE.idle : CONSULTANT_VOICE.emptyCanvas}
      </p>
    </div>
  );
}

function StaleBanner() {
  return (
    <div className="border-b-2 border-[var(--color-warning)] bg-[var(--color-warning)]/10 px-4 py-3 text-sm text-[var(--color-text)]">
      <div className="mb-0.5 flex items-center gap-1.5">
        <span className="text-[var(--color-warning)]">⚠</span>
        <strong>{CONSULTANT_VOICE.staleHeader}</strong>
      </div>
      <div className="text-[var(--color-text-muted)]">
        {CONSULTANT_VOICE.staleBody}
      </div>
    </div>
  );
}

function StreamingView({ text }: { text: string }) {
  const display = text.length > 1500 ? "...\n" + text.slice(-1500) : text;
  return (
    <div className="p-3">
      <div className="mb-2 flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
        <span className="eolgae-pulse inline-block h-2 w-2 rounded-full bg-[var(--color-accent)]" />
        AI 분석 중... 응답 도착 중
      </div>
      <pre className="max-h-52 overflow-auto whitespace-pre-wrap break-all rounded bg-[var(--color-bg-subtle)] p-2.5 font-mono text-xs text-[var(--color-text-muted)]">
        {display}
      </pre>
    </div>
  );
}

function FeedbackView({
  feedback,
  onItemClick,
}: {
  feedback: FeedbackResponse;
  onItemClick?: (item: FeedbackItem) => void;
}) {
  return (
    <>
      {feedback.summary && (
        <div className="border-b border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-4 py-3 text-sm leading-relaxed text-[var(--color-text-muted)]">
          {feedback.summary}
        </div>
      )}
      {feedback.items.length === 0 ? (
        <div className="p-6 text-center text-sm text-[var(--color-text-muted)]">
          발견된 이슈 없음. 좋은 아키텍처입니다.
        </div>
      ) : (
        <div>
          {feedback.items.map((item, i) => (
            <FeedbackRow key={i} item={item} onClick={onItemClick} />
          ))}
        </div>
      )}
    </>
  );
}

function FeedbackRow({
  item,
  onClick,
}: {
  item: FeedbackItem;
  onClick?: (item: FeedbackItem) => void;
}) {
  const sevColor = SEVERITY_COLORS[item.severity];
  const clickable = Boolean(onClick && item.target_node_id);
  return (
    <div
      onClick={clickable ? () => onClick?.(item) : undefined}
      className={[
        "border-b border-[var(--color-border)] px-4 py-2.5",
        clickable
          ? "cursor-pointer hover:bg-[var(--color-bg-subtle)]"
          : "cursor-default",
      ].join(" ")}
    >
      <div className="mb-1 flex items-center gap-2">
        <span
          className="inline-block rounded px-1.5 py-0.5 text-xs font-bold uppercase text-white"
          style={{ background: sevColor }}
        >
          {SEVERITY_LABELS[item.severity]}
        </span>
        <span className="inline-block rounded bg-[var(--color-bg-subtle)] px-1.5 py-0.5 text-xs text-[var(--color-text-muted)]">
          {CATEGORY_LABELS[item.category]}
        </span>
        <strong className="flex-1 text-sm text-[var(--color-text)]">
          {item.title}
        </strong>
        {item.target_node_id && (
          <span className="text-xs text-[var(--color-text-subtle)]">
            노드: {item.target_node_id.slice(0, 8)}…
          </span>
        )}
      </div>
      <div className="text-sm leading-relaxed text-[var(--color-text-muted)]">
        {item.description}
      </div>
      {item.recommendation && (
        <div
          className="mt-1.5 rounded border-l-[3px] bg-[var(--color-accent-soft)] px-2 py-1.5 text-sm text-[var(--color-text)]"
          style={{ borderLeftColor: sevColor }}
        >
          <strong>권장: </strong>
          {item.recommendation}
        </div>
      )}
    </div>
  );
}
