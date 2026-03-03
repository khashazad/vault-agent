import { useEffect } from "react";
import type { ChangesetSummary } from "../types";

interface Props {
  changesets: ChangesetSummary[];
  loading: boolean;
  onRefresh: () => void;
}

function statusColor(status: string): string {
  switch (status) {
    case "applied":
      return "status-applied";
    case "rejected":
      return "status-rejected";
    case "partially_applied":
      return "status-partial";
    default:
      return "status-pending";
  }
}

export function ChangesetHistory({ changesets, loading, onRefresh }: Props) {
  useEffect(() => {
    onRefresh();
  }, [onRefresh]);

  return (
    <div className="changeset-history">
      <div className="history-header">
        <h3>History</h3>
        <button onClick={onRefresh} disabled={loading} className="btn-sm">
          {loading ? "..." : "Refresh"}
        </button>
      </div>

      {changesets.length === 0 ? (
        <p className="empty-state">No changesets yet.</p>
      ) : (
        <div className="history-list">
          {changesets.map((cs) => (
            <div key={cs.id} className="history-item">
              <div className="history-meta">
                <span className={`status-badge ${statusColor(cs.status)}`}>
                  {cs.status}
                </span>
                <span className="history-changes">
                  {cs.change_count} change{cs.change_count !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="history-source">{cs.source}</div>
              <div className="history-time">
                {new Date(cs.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
