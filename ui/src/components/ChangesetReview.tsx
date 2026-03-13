import { useState, useEffect, useCallback, useRef } from "react";
import type { ProposedChange } from "../types";
import {
  fetchChangeset,
  updateChangeStatus,
  updateChangeContent,
  applyChangeset,
  rejectChangeset,
} from "../api/client";
import { formatError } from "../utils";
import { DiffViewer } from "./DiffViewer";
import { MarkdownPreview } from "./MarkdownPreview";

type ViewMode = "diff" | "preview" | "edit";

interface Props {
  changesetId: string;
  initialChanges: ProposedChange[];
  onDone: () => void;
  readOnly?: boolean;
}

export function ChangesetReview({ changesetId, initialChanges, onDone, readOnly = false }: Props) {
  const [changes, setChanges] = useState<ProposedChange[]>(
    readOnly ? initialChanges : initialChanges.map((c) => ({ ...c, status: "approved" }))
  );
  const [viewModes, setViewModes] = useState<Record<string, ViewMode>>({});
  const [editBuffers, setEditBuffers] = useState<Record<string, string>>({});
  const [applying, setApplying] = useState(false);
  const [loadingChangeset, setLoadingChangeset] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    applied: string[];
    failed: { id: string; error: string }[];
  } | null>(null);

  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // If no initial changes provided, fetch from server
  useEffect(() => {
    if (initialChanges.length === 0 && changesetId) {
      setLoadingChangeset(true);
      setFetchError(null);
      fetchChangeset(changesetId)
        .then((cs) => {
          if (readOnly) {
            setChanges(cs.changes);
          } else {
            const approvedChanges = cs.changes.map((c) => ({ ...c, status: "approved" as const }));
            setChanges(approvedChanges);
            approvedChanges.forEach((c) => {
              updateChangeStatus(changesetId, c.id, "approved").catch((err) =>
                setStatusError(formatError(err))
              );
            });
          }
        })
        .catch((err) => setFetchError(String(err)))
        .finally(() => setLoadingChangeset(false));
    } else if (!readOnly) {
      // Set all changes to approved by default on the server
      initialChanges.forEach((c) => {
        updateChangeStatus(changesetId, c.id, "approved").catch((err) => setStatusError(formatError(err)));
      });
    }
  }, [changesetId, initialChanges, readOnly]);

  const toggleChange = useCallback(
    async (changeId: string) => {
      if (readOnly) return;
      setChanges((prev) =>
        prev.map((c) => {
          if (c.id !== changeId) return c;
          const newStatus = c.status === "approved" ? "rejected" : "approved";
          updateChangeStatus(changesetId, changeId, newStatus).catch((err) => setStatusError(formatError(err)));
          return { ...c, status: newStatus };
        })
      );
    },
    [changesetId, readOnly]
  );

  const setAllStatuses = useCallback(
    (status: "approved" | "rejected") => {
      if (readOnly) return;
      setChanges((prev) =>
        prev.map((c) => {
          updateChangeStatus(changesetId, c.id, status).catch((err) => setStatusError(formatError(err)));
          return { ...c, status };
        })
      );
    },
    [changesetId, readOnly]
  );

  const handleEditChange = useCallback(
    (changeId: string, content: string) => {
      setEditBuffers((prev) => ({ ...prev, [changeId]: content }));

      // Debounce the API call
      if (debounceTimers.current[changeId]) {
        clearTimeout(debounceTimers.current[changeId]);
      }
      debounceTimers.current[changeId] = setTimeout(async () => {
        try {
          await updateChangeContent(changesetId, changeId, content);
          // Refetch to get updated diff
          const cs = await fetchChangeset(changesetId);
          setChanges((prev) =>
            prev.map((c) => {
              const updated = cs.changes.find((uc) => uc.id === c.id);
              return updated ? { ...updated, status: c.status } : c;
            })
          );
        } catch (err) {
          setStatusError(formatError(err));
        }
      }, 500);
    },
    [changesetId]
  );

  const handleApply = useCallback(async () => {
    const approvedIds = changes.filter((c) => c.status === "approved").map((c) => c.id);

    if (approvedIds.length === 0) return;

    setApplying(true);
    try {
      const res = await applyChangeset(changesetId, approvedIds);
      setResult(res);
    } catch (err) {
      setResult({
        applied: [],
        failed: [{ id: "all", error: String(err) }],
      });
    } finally {
      setApplying(false);
    }
  }, [changesetId, changes]);

  const handleReject = useCallback(async () => {
    await rejectChangeset(changesetId);
    onDone();
  }, [changesetId, onDone]);

  const approvedCount = changes.filter((c) => c.status === "approved").length;

  if (loadingChangeset) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-red mb-3">Failed to load changeset: {fetchError}</p>
        <button onClick={onDone} className="bg-accent text-crust border-none py-2 px-5 rounded text-sm">
          Back
        </button>
      </div>
    );
  }

  if (changes.length === 0) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-muted mb-3">The agent completed without proposing any changes.</p>
        <button onClick={onDone} className="bg-accent text-crust border-none py-2 px-5 rounded text-sm">
          Done
        </button>
      </div>
    );
  }

  if (result) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <h3>Changes Applied</h3>
        {result.applied.length > 0 && (
          <p className="text-green mb-3">{result.applied.length} change(s) applied successfully.</p>
        )}
        {result.failed.length > 0 && (
          <div>
            <p className="text-red">{result.failed.length} change(s) failed:</p>
            <ul>
              {result.failed.map((f) => (
                <li key={f.id}>{f.error}</li>
              ))}
            </ul>
          </div>
        )}
        <button onClick={onDone} className="mt-4 bg-accent text-crust border-none py-2 px-5 rounded text-sm">
          Start New
        </button>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-border rounded p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm">Review Changes ({changes.length})</h3>
        {!readOnly && (
          <div className="flex gap-2">
            <button
              onClick={() => setAllStatuses("approved")}
              className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs"
            >
              Approve All
            </button>
            <button
              onClick={() => setAllStatuses("rejected")}
              className="bg-transparent text-text border border-border py-1 px-3 rounded text-xs"
            >
              Reject All
            </button>
          </div>
        )}
      </div>

      {statusError && <p className="text-red text-xs mb-2">Failed to update status: {statusError}</p>}

      <div className="flex flex-col gap-3 mb-4">
        {changes.map((change) => {
          const mode = viewModes[change.id] ?? (change.tool_name === "create_note" ? "preview" : "diff");
          return (
            <div key={change.id} className="relative">
              <div className="flex items-center gap-2 mb-1">
                {!readOnly ? (
                  <button
                    onClick={() => toggleChange(change.id)}
                    className={`w-7 h-7 rounded-full border-2 bg-bg text-muted flex items-center justify-center text-sm ${
                      change.status === "approved"
                        ? "border-green text-green bg-green-bg"
                        : change.status === "rejected"
                          ? "border-red text-red bg-red-bg"
                          : "border-border"
                    }`}
                  >
                    {change.status === "approved" ? "\u2713" : "\u2717"}
                  </button>
                ) : null}
                <span className="text-xs text-muted uppercase">{change.status}</span>
                <div className="ml-auto flex border border-border rounded overflow-hidden">
                  <button
                    onClick={() => setViewModes((prev) => ({ ...prev, [change.id]: "diff" }))}
                    className={`text-[11px] py-0.5 px-2.5 border-none ${mode === "diff" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                  >
                    Diff
                  </button>
                  <button
                    onClick={() => setViewModes((prev) => ({ ...prev, [change.id]: "preview" }))}
                    className={`text-[11px] py-0.5 px-2.5 border-none ${mode === "preview" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                  >
                    Preview
                  </button>
                  {!readOnly && (
                    <button
                      onClick={() => setViewModes((prev) => ({ ...prev, [change.id]: "edit" }))}
                      className={`text-[11px] py-0.5 px-2.5 border-none ${mode === "edit" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                    >
                      Edit
                    </button>
                  )}
                </div>
              </div>
              {mode === "diff" ? (
                <DiffViewer
                  diff={change.diff}
                  filePath={change.input.path as string}
                  isNew={change.tool_name === "create_note"}
                  originalContent={change.original_content}
                  proposedContent={change.proposed_content}
                />
              ) : mode === "preview" ? (
                <MarkdownPreview content={change.proposed_content} />
              ) : (
                <textarea
                  className="w-full h-64 bg-bg border border-border rounded p-3 text-sm text-foreground font-mono resize-y outline-none focus:border-accent"
                  value={editBuffers[change.id] ?? change.proposed_content}
                  onChange={(e) => handleEditChange(change.id, e.target.value)}
                />
              )}
            </div>
          );
        })}
      </div>

      {!readOnly && (
        <div className="flex gap-3 pt-4 border-t border-border">
          <button
            onClick={handleApply}
            disabled={applying || approvedCount === 0}
            className="bg-green text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {applying ? "Applying..." : `Apply ${approvedCount} Change${approvedCount !== 1 ? "s" : ""}`}
          </button>
          <button
            onClick={handleReject}
            className="bg-transparent text-red border border-red py-2 px-5 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={applying}
          >
            Reject All & Discard
          </button>
        </div>
      )}
    </div>
  );
}
