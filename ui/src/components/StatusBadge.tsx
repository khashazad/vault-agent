export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-accent/15 text-accent",
  applied: "bg-green-bg text-green",
  rejected: "bg-red-bg text-red",
  partially_applied: "bg-accent/15 text-accent",
  skipped: "bg-surface text-muted border border-border",
  revision_requested: "bg-accent/15 text-yellow",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[status] ?? "bg-surface text-muted"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
