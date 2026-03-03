import { useState, useCallback } from "react";
import type { HighlightInput, AgentStreamEvent, ProposedChange } from "../types";
import { streamPreview } from "../api/sse";

export type StreamStatus = "idle" | "streaming" | "complete" | "error";

export interface ToolCallEvent {
  tool_name: string;
  input: Record<string, unknown>;
  result?: string;
  is_error?: boolean;
}

export function useAgentStream() {
  const [reasoning, setReasoning] = useState("");
  const [toolCalls, setToolCalls] = useState<ToolCallEvent[]>([]);
  const [proposedChanges, setProposedChanges] = useState<ProposedChange[]>([]);
  const [changesetId, setChangesetId] = useState<string | null>(null);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setReasoning("");
    setToolCalls([]);
    setProposedChanges([]);
    setChangesetId(null);
    setStatus("idle");
    setError(null);
  }, []);

  const start = useCallback(async (highlight: HighlightInput) => {
    reset();
    setStatus("streaming");

    await streamPreview(
      highlight,
      (event: AgentStreamEvent) => {
        switch (event.type) {
          case "reasoning":
            setReasoning((prev) => prev + (event.data.text as string));
            break;
          case "tool_call":
            setToolCalls((prev) => [
              ...prev,
              {
                tool_name: event.data.tool_name as string,
                input: event.data.input as Record<string, unknown>,
              },
            ]);
            break;
          case "tool_result":
            setToolCalls((prev) => {
              if (prev.length === 0) return prev;
              const last = prev[prev.length - 1];
              return [
                ...prev.slice(0, -1),
                { ...last, result: event.data.result as string, is_error: event.data.is_error as boolean },
              ];
            });
            break;
          case "proposed_change":
            setProposedChanges((prev) => [
              ...prev,
              event.data as unknown as ProposedChange,
            ]);
            break;
          case "complete":
            setChangesetId(event.data.changeset_id as string);
            setStatus("complete");
            break;
          case "error":
            setError(event.data.message as string);
            setStatus("error");
            break;
        }
      },
      () => {
        setStatus((prev) => (prev === "streaming" ? "complete" : prev));
      },
      (err) => {
        setError(err);
        setStatus("error");
      }
    );
  }, [reset]);

  return {
    reasoning,
    toolCalls,
    proposedChanges,
    changesetId,
    status,
    error,
    start,
    reset,
  };
}
