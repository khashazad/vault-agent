export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-accent/15 text-accent",
  applied: "bg-green-bg text-green",
  rejected: "bg-red-bg text-red",
  partially_applied: "bg-accent/15 text-accent",
  skipped: "bg-surface text-muted border border-border",
  revision_requested: "bg-accent/15 text-yellow",
  migrating: "bg-blue-500/15 text-blue-400",
  review: "bg-green-bg text-green",
  applying: "bg-accent/15 text-accent",
  completed: "bg-green-bg text-green",
  failed: "bg-red-bg text-red",
  cancelled: "bg-surface text-muted border border-border",
  processing: "bg-blue-500/15 text-blue-400",
  proposed: "bg-yellow-bg text-yellow",
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
