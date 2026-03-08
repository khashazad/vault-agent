export function formatError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function confidenceClass(confidence: number): string {
  if (confidence >= 0.8) return "text-green";
  if (confidence >= 0.5) return "text-yellow";
  return "text-red";
}

export function routingActionClass(action: "update" | "create" | "skip"): string {
  if (action === "update") return "bg-blue-bg text-blue";
  if (action === "skip") return "bg-yellow-bg text-yellow";
  return "bg-green-bg text-green";
}
