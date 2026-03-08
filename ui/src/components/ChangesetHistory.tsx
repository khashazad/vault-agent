import { useEffect } from "react";
import type { ChangesetSummary } from "../types";
import { routingActionClass } from "../utils";
import { StatusBadge } from "./StatusBadge";

interface Props {
  changesets: ChangesetSummary[];
  loading: boolean;
  onRefresh: () => void;
}

export function ChangesetHistory({ changesets, loading, onRefresh }: Props) {
  useEffect(() => {
    onRefresh();
  }, [onRefresh]);

  return (
    <div className="bg-surface border border-border rounded p-4 max-w-[960px] mx-auto">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm">History</h3>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs"
        >
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      {changesets.length === 0 ? (
        <p className="text-muted text-center py-8">No history yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {changesets.map((cs) => (
            <div key={cs.id} className="border border-border rounded p-3">
              <div className="flex items-center gap-2 mb-1">
                <StatusBadge status={cs.status} />
                {cs.routing_action && (
                  <span
                    className={`text-[11px] font-semibold py-0.5 px-2 rounded-[3px] uppercase ${routingActionClass(cs.routing_action)}`}
                  >
                    {cs.routing_action}
                  </span>
                )}
                <span className="text-xs text-muted">
                  {cs.highlight_count > 1 &&
                    `${cs.highlight_count} snippets · `}
                  {cs.change_count} change{cs.change_count !== 1 ? "s" : ""}
                </span>
              </div>
              {cs.routing_target && (
                <div className="font-mono text-[13px] text-accent mb-0.5">
                  {cs.routing_target}
                </div>
              )}
              <div className="text-[13px] text-text mb-0.5">{cs.source}</div>
              <div className="text-xs text-muted">
                {new Date(cs.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
