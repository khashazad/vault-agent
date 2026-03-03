import { useEffect, useRef } from "react";
import type { ToolCallEvent } from "../hooks/useAgentStream";

interface Props {
  reasoning: string;
  toolCalls: ToolCallEvent[];
  isStreaming: boolean;
}

export function AgentStream({ reasoning, toolCalls, isStreaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [reasoning, toolCalls]);

  if (!reasoning && toolCalls.length === 0) return null;

  return (
    <div className="agent-stream">
      <h3>
        Agent Reasoning {isStreaming && <span className="pulse">&#9679;</span>}
      </h3>

      {toolCalls.length > 0 && (
        <div className="tool-calls">
          {toolCalls.map((tc, i) => (
            <div
              key={i}
              className={`tool-call ${tc.tool_name === "read_note" ? "read" : "write"}`}
            >
              <div className="tool-call-header">
                <span className="tool-badge">{tc.tool_name}</span>
                <span className="tool-path">
                  {(tc.input.path as string) || ""}
                </span>
              </div>
              {tc.result && (
                <div
                  className={`tool-result ${tc.is_error ? "error" : ""}`}
                >
                  {tc.is_error ? "Error: " : ""}
                  {tc.result.length > 200
                    ? tc.result.slice(0, 200) + "..."
                    : tc.result}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {reasoning && (
        <div className="reasoning-text">
          <pre>{reasoning}</pre>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
