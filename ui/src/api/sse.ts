import type { HighlightInput, AgentStreamEvent } from "../types";

export async function streamPreview(
  highlight: HighlightInput,
  onEvent: (event: AgentStreamEvent) => void,
  onDone: () => void,
  onError: (error: string) => void
): Promise<void> {
  const res = await fetch("/highlights/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(highlight),
  });

  if (!res.ok) {
    const text = await res.text();
    onError(text);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const dataStr = line.slice(6);
        try {
          const parsed = JSON.parse(dataStr) as AgentStreamEvent;
          onEvent(parsed);
        } catch {
          // Ignore parse errors
        }
      }
    }
  }

  onDone();
}
