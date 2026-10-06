import {
  API_URL,
  authHeaders,
  type FeedbackResponse,
  type ReviewContext,
} from "@/lib/api";

export interface FeedbackStreamCallbacks {
  onDelta: (text: string) => void;
  onComplete: (response: FeedbackResponse) => void;
  onError: (message: string) => void;
}

export async function streamFeedback(
  id: string,
  reviewContext: ReviewContext | undefined,
  callbacks: FeedbackStreamCallbacks,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const res = await fetch(`${API_URL}/canvas/${id}/feedback/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({ review_context: reviewContext ?? null }),
    signal: options?.signal,
  });

  if (!res.ok || !res.body) {
    let detail = "";
    try {
      const data = await res.json();
      detail = data.detail || "";
    } catch {
      // ignore
    }
    throw new Error(
      `stream failed: ${res.status}${detail ? ` - ${detail}` : ""}`,
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const event of events) {
        for (const line of event.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "delta") {
              callbacks.onDelta(data.content);
            } else if (data.type === "complete") {
              callbacks.onComplete({
                items: data.items,
                summary: data.summary,
                canvas_hash: data.canvas_hash,
              });
            } else if (data.type === "error") {
              callbacks.onError(data.message);
            }
          } catch (e) {
            console.error("SSE parse error", e, line);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
