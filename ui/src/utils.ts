export function formatError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}
