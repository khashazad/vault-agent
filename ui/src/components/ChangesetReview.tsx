import { useState, useEffect, useCallback } from "react";
import type { ProposedChange, Changeset } from "../types";
import { fetchChangeset, updateChangeStatus, applyChangeset, rejectChangeset } from "../api/client";
import { DiffViewer } from "./DiffViewer";

interface Props {
  changesetId: string;
  initialChanges: ProposedChange[];
  onDone: () => void;
}

export function ChangesetReview({ changesetId, initialChanges, onDone }: Props) {
  const [changes, setChanges] = useState<ProposedChange[]>(
    initialChanges.map((c) => ({ ...c, status: "approved" }))
  );
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<{
    applied: string[];
    failed: { id: string; error: string }[];
  } | null>(null);

  // Set all changes to approved by default on the server
  useEffect(() => {
    changes.forEach((c) => {
      updateChangeStatus(changesetId, c.id, "approved").catch(() => {});
    });
  }, []);

  const toggleChange = useCallback(
    async (changeId: string) => {
      setChanges((prev) =>
        prev.map((c) => {
          if (c.id !== changeId) return c;
          const newStatus = c.status === "approved" ? "rejected" : "approved";
          updateChangeStatus(changesetId, changeId, newStatus).catch(() => {});
          return { ...c, status: newStatus };
        })
      );
    },
    [changesetId]
  );

  const approveAll = useCallback(() => {
    setChanges((prev) =>
      prev.map((c) => {
        updateChangeStatus(changesetId, c.id, "approved").catch(() => {});
        return { ...c, status: "approved" };
      })
    );
  }, [changesetId]);

  const rejectAll = useCallback(() => {
    setChanges((prev) =>
      prev.map((c) => {
        updateChangeStatus(changesetId, c.id, "rejected").catch(() => {});
        return { ...c, status: "rejected" };
      })
    );
  }, [changesetId]);

  const handleApply = useCallback(async () => {
    const approvedIds = changes
      .filter((c) => c.status === "approved")
      .map((c) => c.id);

    if (approvedIds.length === 0) return;

    setApplying(true);
    try {
      const res = await applyChangeset(changesetId, approvedIds);
      setResult(res);
    } catch (err) {
      setResult({ applied: [], failed: [{ id: "all", error: String(err) }] });
    } finally {
      setApplying(false);
    }
  }, [changesetId, changes]);

  const handleReject = useCallback(async () => {
    await rejectChangeset(changesetId);
    onDone();
  }, [changesetId, onDone]);

  const approvedCount = changes.filter((c) => c.status === "approved").length;

  if (result) {
    return (
      <div className="changeset-result">
        <h3>Changes Applied</h3>
        {result.applied.length > 0 && (
          <p className="success">
            {result.applied.length} change(s) applied successfully.
          </p>
        )}
        {result.failed.length > 0 && (
          <div className="failures">
            <p className="error">{result.failed.length} change(s) failed:</p>
            <ul>
              {result.failed.map((f) => (
                <li key={f.id}>{f.error}</li>
              ))}
            </ul>
          </div>
        )}
        <button onClick={onDone}>Start New</button>
      </div>
    );
  }

  return (
    <div className="changeset-review">
      <div className="review-header">
        <h3>Review Changes ({changes.length})</h3>
        <div className="review-actions">
          <button onClick={approveAll} className="btn-sm">
            Approve All
          </button>
          <button onClick={rejectAll} className="btn-sm btn-outline">
            Reject All
          </button>
        </div>
      </div>

      <div className="changes-list">
        {changes.map((change) => (
          <div
            key={change.id}
            className={`change-item ${change.status}`}
          >
            <div className="change-toggle">
              <button
                onClick={() => toggleChange(change.id)}
                className={`toggle-btn ${change.status}`}
              >
                {change.status === "approved" ? "\u2713" : "\u2717"}
              </button>
              <span className="change-status-label">{change.status}</span>
            </div>
            <DiffViewer
              diff={change.diff}
              filePath={change.input.path as string}
              isNew={change.tool_name === "create_note"}
            />
          </div>
        ))}
      </div>

      <div className="review-footer">
        <button
          onClick={handleApply}
          disabled={applying || approvedCount === 0}
          className="btn-primary"
        >
          {applying
            ? "Applying..."
            : `Apply ${approvedCount} Change${approvedCount !== 1 ? "s" : ""}`}
        </button>
        <button onClick={handleReject} className="btn-danger" disabled={applying}>
          Reject All & Discard
        </button>
      </div>
    </div>
  );
}
