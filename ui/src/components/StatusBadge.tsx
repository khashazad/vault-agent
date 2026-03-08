const STATUS_COLORS: Record<string, string> = {
  applied: "bg-green-bg text-green",
  rejected: "bg-red-bg text-red",
  partially_applied: "bg-yellow-bg text-yellow",
  skipped: "bg-yellow-bg text-yellow",
};

const DEFAULT_COLOR = "bg-yellow-bg text-yellow";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-[11px] font-semibold py-0.5 px-2 rounded-[10px] uppercase ${STATUS_COLORS[status] ?? DEFAULT_COLOR}`}
    >
      {status}
    </span>
  );
}
