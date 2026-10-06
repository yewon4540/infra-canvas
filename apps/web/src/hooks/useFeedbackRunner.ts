import { useCallback, useRef, useState } from "react";

import {
  type FeedbackItem,
  type FeedbackResponse,
  type ReviewContext,
} from "@/lib/api";
import { streamFeedback } from "@/lib/feedback-api";

type UseFeedbackRunnerArgs = {
  canvasId?: string;
  canvasFingerprint: string;
  onSelectNode: (nodeId: string) => void;
};

export function useFeedbackRunner({
  canvasId,
  canvasFingerprint,
  onSelectNode,
}: UseFeedbackRunnerArgs) {
  const [feedback, setFeedback] = useState<FeedbackResponse | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [analyzedFingerprint, setAnalyzedFingerprint] = useState<string | null>(
    null,
  );
  const [autoReflect, setAutoReflect] = useState(true);
  const feedbackAbortRef = useRef<AbortController | null>(null);

  const isStale =
    analyzedFingerprint !== null && analyzedFingerprint !== canvasFingerprint;

  const requestFeedback = useCallback(async (reviewContext?: ReviewContext) => {
    if (!canvasId) return;
    if (feedbackAbortRef.current) return;
    const controller = new AbortController();
    feedbackAbortRef.current = controller;
    const snapshotAtStart = canvasFingerprint;
    setFeedbackOpen(true);
    setFeedbackLoading(true);
    setFeedbackError(null);
    setFeedback(null);
    setStreamingText("");
    try {
      await streamFeedback(
        canvasId,
        reviewContext,
        {
          onDelta: (text) => setStreamingText((prev) => prev + text),
          onComplete: (response) => {
            setFeedback(response);
            setStreamingText("");
            setAnalyzedFingerprint(snapshotAtStart);
          },
          onError: (msg) => setFeedbackError(msg),
        },
        { signal: controller.signal },
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setFeedbackError((e as Error).message);
      }
    } finally {
      feedbackAbortRef.current = null;
      setFeedbackLoading(false);
    }
  }, [canvasId, canvasFingerprint]);

  const stopFeedback = useCallback(() => {
    feedbackAbortRef.current?.abort();
    feedbackAbortRef.current = null;
    setFeedbackLoading(false);
    setStreamingText("");
  }, []);

  const openFeedbackPanel = useCallback(() => {
    setFeedbackOpen(true);
  }, []);

  const handleFeedbackItemClick = useCallback(
    (item: FeedbackItem) => {
      if (item.target_node_id) {
        onSelectNode(item.target_node_id);
      }
    },
    [onSelectNode],
  );

  return {
    feedback,
    feedbackLoading,
    feedbackError,
    feedbackOpen,
    setFeedbackOpen,
    streamingText,
    isStale,
    autoReflect,
    setAutoReflect,
    requestFeedback,
    stopFeedback,
    openFeedbackPanel,
    handleFeedbackItemClick,
  };
}
