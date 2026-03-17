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
import { Skeleton } from "./Skeleton";

type ViewMode = "diff" | "preview" | "edit";

interface Props {
  changesetId: string;
  initialChanges: ProposedChange[];
  onDone: () => void;
  readOnly?: boolean;
}

export function ChangesetReview({
  changesetId,
  initialChanges,
  onDone,
  readOnly = false,
}: Props) {
  const [changes, setChanges] = useState<ProposedChange[]>(
    readOnly
      ? initialChanges
      : initialChanges.map((c) => ({ ...c, status: "approved" })),
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

  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );

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
            const approvedChanges = cs.changes.map((c) => ({
              ...c,
              status: "approved" as const,
            }));
            setChanges(approvedChanges);
            approvedChanges.forEach((c) => {
              updateChangeStatus(changesetId, c.id, "approved").catch((err) =>
                setStatusError(formatError(err)),
              );
            });
          }
        })
        .catch((err) => setFetchError(String(err)))
        .finally(() => setLoadingChangeset(false));
    } else if (!readOnly) {
      // Set all changes to approved by default on the server
      initialChanges.forEach((c) => {
        updateChangeStatus(changesetId, c.id, "approved").catch((err) =>
          setStatusError(formatError(err)),
        );
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
          updateChangeStatus(changesetId, changeId, newStatus).catch((err) =>
            setStatusError(formatError(err)),
          );
          return { ...c, status: newStatus };
        }),
      );
    },
    [changesetId, readOnly],
  );

  const setAllStatuses = useCallback(
    (status: "approved" | "rejected") => {
      if (readOnly) return;
      setChanges((prev) =>
        prev.map((c) => {
          updateChangeStatus(changesetId, c.id, status).catch((err) =>
            setStatusError(formatError(err)),
          );
          return { ...c, status };
        }),
      );
    },
    [changesetId, readOnly],
  );

  const handleEditChange = useCallback(
    (changeId: string, content: string) => {
      setEditBuffers((prev) => ({ ...prev, [changeId]: content }));
      setSavingIds((prev) => new Set(prev).add(changeId));

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
            }),
          );
        } catch (err) {
          setStatusError(formatError(err));
        } finally {
          setSavingIds((prev) => {
            const next = new Set(prev);
            next.delete(changeId);
            return next;
          });
        }
      }, 500);
    },
    [changesetId],
  );

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
      <div className="bg-surface border border-border rounded p-4 flex flex-col gap-3">
        <div className="flex gap-3">
          <Skeleton h="h-4" w="w-24" />
          <Skeleton h="h-4" w="w-32" />
        </div>
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} h="h-3" w={i % 2 === 0 ? "w-full" : "w-3/4"} />
        ))}
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-red mb-3">Failed to load changeset: {fetchError}</p>
        <button
          onClick={onDone}
          className="bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Back
        </button>
      </div>
    );
  }

  if (changes.length === 0) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-muted mb-3">
          The agent completed without proposing any changes.
        </p>
        <button
          onClick={onDone}
          className="bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Done
        </button>
      </div>
    );
  }

  if (result) {
    const targetPaths = changes
      .filter((c) => result.applied.includes(c.id))
      .map((c) => c.input.path as string);

    return (
      <div className="bg-surface border border-border rounded p-5 flex flex-col items-center gap-3">
        {result.applied.length > 0 && (
          <>
            <svg
              width="32"
              height="32"
              viewBox="0 0 16 16"
              fill="currentColor"
              className="text-green"
            >
              <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0m3.78 4.97a.75.75 0 0 0-1.06 0L7 8.69 5.28 6.97a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25a.75.75 0 0 0 0-1.06" />
            </svg>
            <h3 className="text-sm font-semibold m-0">
              {result.applied.length} change
              {result.applied.length !== 1 ? "s" : ""} written to vault
            </h3>
            {targetPaths.length > 0 && (
              <div className="flex flex-col gap-1">
                {targetPaths.map((p) => (
                  <span key={p} className="text-xs font-mono text-muted">
                    {p}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
        {result.failed.length > 0 && (
          <div className="text-center">
            <p className="text-red text-sm">
              {result.failed.length} change(s) failed:
            </p>
            <ul className="text-xs text-red list-none p-0">
              {result.failed.map((f) => (
                <li key={f.id}>{f.error}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          onClick={onDone}
          className="mt-2 bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Start New
        </button>
      </div>
    );
  }

  const isSingle = changes.length === 1;

  return (
    <div className="bg-surface border border-border rounded p-4 flex flex-col flex-1 min-h-0">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm">
          {isSingle ? "Review Change" : `Review Changes (${changes.length})`}
        </h3>
        {!readOnly && !isSingle && (
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

      {statusError && (
        <p className="text-red text-xs mb-2">
          Failed to update status: {statusError}
        </p>
      )}

      <div className="flex flex-col gap-3 mb-4 flex-1 min-h-0">
        {changes.map((change) => {
          const mode =
            viewModes[change.id] ??
            (change.tool_name === "create_note" ? "preview" : "diff");
          return (
            <div
              key={change.id}
              className="relative flex flex-col flex-1 min-h-0"
            >
              <div className="flex items-center gap-2 mb-1">
                {!readOnly && !isSingle ? (
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
                {!isSingle && (
                  <span className="text-xs text-muted uppercase">
                    {change.status}
                  </span>
                )}
                <div
                  className={`${isSingle ? "" : "ml-auto "}flex border border-border rounded overflow-hidden`}
                >
                  {change.tool_name !== "create_note" && (
                    <button
                      onClick={() =>
                        setViewModes((prev) => ({
                          ...prev,
                          [change.id]: "diff",
                        }))
                      }
                      className={`text-[11px] py-0.5 px-2.5 border-none ${mode === "diff" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                    >
                      Diff
                    </button>
                  )}
                  <button
                    onClick={() =>
                      setViewModes((prev) => ({
                        ...prev,
                        [change.id]: "preview",
                      }))
                    }
                    className={`text-[11px] py-0.5 px-2.5 border-none ${mode === "preview" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                  >
                    Preview
                  </button>
                  {!readOnly && (
                    <button
                      onClick={() =>
                        setViewModes((prev) => ({
                          ...prev,
                          [change.id]: "edit",
                        }))
                      }
                      className={`text-[11px] py-0.5 px-2.5 border-none ${mode === "edit" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                    >
                      Edit
                    </button>
                  )}
                </div>
                {mode === "edit" && savingIds.has(change.id) && (
                  <span className="text-[10px] text-muted animate-pulse ml-2">
                    Saving...
                  </span>
                )}
              </div>
              {mode === "diff" && change.tool_name !== "create_note" ? (
                <DiffViewer
                  diff={change.diff}
                  filePath={change.input.path as string}
                  isNew={false}
                  originalContent={change.original_content}
                  proposedContent={change.proposed_content}
                />
              ) : mode === "edit" && !readOnly ? (
                <textarea
                  className="w-full flex-1 min-h-64 bg-bg border border-border rounded p-3 text-sm text-foreground font-mono resize-y outline-none focus:border-accent"
                  value={editBuffers[change.id] ?? change.proposed_content}
                  onChange={(e) => handleEditChange(change.id, e.target.value)}
                />
              ) : (
                <MarkdownPreview content={change.proposed_content} />
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
            {applying
              ? "Applying..."
              : isSingle
                ? "Approve"
                : `Apply ${approvedCount} Change${approvedCount !== 1 ? "s" : ""}`}
          </button>
          <button
            onClick={handleReject}
            className="bg-transparent text-red border border-red py-2 px-5 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={applying}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
