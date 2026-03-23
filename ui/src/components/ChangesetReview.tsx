import { useState, useEffect, useCallback, useRef } from "react";
import type { ProposedChange } from "../types";
import {
  fetchChangeset,
  updateChangeStatus,
  updateChangeContent,
  applyChangeset,
  rejectChangeset,
  convergeClawdy,
} from "../api/client";
import type { SourceType } from "../types";
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
  sourceType?: SourceType;
}

export function ChangesetReview({
  changesetId,
  initialChanges,
  onDone,
  readOnly = false,
  sourceType,
}: Props) {
  const [changes, setChanges] = useState<ProposedChange[]>(initialChanges);
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
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>(
    {},
  );
  // Track which changes have been synced to server to avoid redundant calls
  const syncedIds = useRef<Set<string>>(new Set());

  // If no initial changes provided, fetch from server
  useEffect(() => {
    if (initialChanges.length === 0 && changesetId) {
      setLoadingChangeset(true);
      setFetchError(null);
      fetchChangeset(changesetId)
        .then((cs) => setChanges(cs.changes))
        .catch((err) => setFetchError(String(err)))
        .finally(() => setLoadingChangeset(false));
    }
  }, [changesetId, initialChanges]);

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
      setChanges((prev) => prev.map((c) => ({ ...c, status })));
      // Mark all as needing sync; actual sync happens on apply
      syncedIds.current.clear();
    },
    [readOnly],
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
      // Sync statuses to server before applying (batched, 10 at a time)
      const unsyncedChanges = changes.filter(
        (c) =>
          !syncedIds.current.has(c.id) &&
          (c.status === "approved" || c.status === "rejected"),
      );
      for (let i = 0; i < unsyncedChanges.length; i += 10) {
        const batch = unsyncedChanges.slice(i, i + 10);
        await Promise.all(
          batch.map((c) =>
            updateChangeStatus(
              changesetId,
              c.id,
              c.status as "approved" | "rejected",
            ),
          ),
        );
      }

      const res = await applyChangeset(changesetId, approvedIds);
      setResult(res);
      if (sourceType === "clawdy") {
        try {
          await convergeClawdy(changesetId);
        } catch (convergeErr) {
          setStatusError(
            `Applied to vault but copy-vault sync failed: ${formatError(convergeErr)}`,
          );
        }
      }
    } catch (err) {
      setResult({
        applied: [],
        failed: [{ id: "all", error: String(err) }],
      });
    } finally {
      setApplying(false);
    }
  }, [changesetId, changes, sourceType]);

  const handleReject = useCallback(async () => {
    try {
      await rejectChangeset(changesetId);
      if (sourceType === "clawdy") {
        await convergeClawdy(changesetId);
      }
    } catch (err) {
      setStatusError(formatError(err));
      return;
    }
    onDone();
  }, [changesetId, onDone, sourceType]);

  const approvedCount = changes.filter((c) => c.status === "approved").length;

  const setChangeStatus = useCallback(
    (changeId: string, status: "approved" | "rejected" | "pending") => {
      if (readOnly) return;
      setChanges((prev) =>
        prev.map((c) => (c.id === changeId ? { ...c, status } : c)),
      );
      syncedIds.current.delete(changeId);
    },
    [readOnly],
  );

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
  const pendingChanges = changes.filter((c) => c.status === "pending");
  const reviewedChanges = changes.filter(
    (c) => c.status === "approved" || c.status === "rejected",
  );

  function renderRow(change: ProposedChange, isReviewed: boolean) {
    const isExpanded = isSingle || expandedId === change.id;
    const mode =
      viewModes[change.id] ??
      (change.tool_name === "create_note" ? "preview" : "diff");
    const filePath = change.input.path as string;
    const toolLabel =
      change.tool_name === "create_note"
        ? "NEW"
        : change.tool_name === "delete_note"
          ? "DEL"
          : "MOD";
    const toolBadgeClass =
      change.tool_name === "create_note"
        ? "bg-green/10 text-green"
        : change.tool_name === "delete_note"
          ? "bg-red/10 text-red"
          : "bg-yellow/10 text-yellow";

    return (
      <div
        key={change.id}
        className={`overflow-hidden transition-all border-l-2 ${
          isSingle
            ? "flex flex-col flex-1 min-h-0 border-l-0"
            : isExpanded
              ? "border-accent bg-surface"
              : isReviewed
                ? "border-transparent opacity-70 hover:opacity-100 hover:border-muted/50"
                : "border-transparent hover:border-accent/50"
        }`}
      >
        {/* Row header */}
        <div
          className={`px-4 py-3 flex items-center justify-between ${
            isSingle ? "" : "cursor-pointer"
          }`}
          onClick={
            isSingle
              ? undefined
              : () => setExpandedId(expandedId === change.id ? null : change.id)
          }
        >
          <div className="flex items-center gap-2 min-w-0">
            {isReviewed && (
              <span
                className={`text-xs flex-shrink-0 ${change.status === "approved" ? "text-green" : "text-red"}`}
              >
                {change.status === "approved" ? "\u2713" : "\u2717"}
              </span>
            )}
            <span
              className={`text-sm font-mono truncate ${isReviewed ? "text-muted" : "text-foreground"}`}
            >
              {filePath}
            </span>
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${toolBadgeClass}`}
            >
              {toolLabel}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0 ml-3">
            {!readOnly && !isReviewed && (
              <>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setChangeStatus(change.id, "approved");
                  }}
                  className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted hover:bg-green/10 hover:text-green"
                >
                  &#10003; Approve
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setChangeStatus(change.id, "rejected");
                  }}
                  className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted/60 hover:bg-red/10 hover:text-red"
                >
                  &#10005; Reject
                </button>
              </>
            )}
            {!readOnly && isReviewed && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setChangeStatus(change.id, "pending");
                }}
                className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted hover:bg-accent/10 hover:text-accent"
              >
                &#8634; Undo
              </button>
            )}
            {!readOnly && !isSingle && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedId(change.id);
                  setViewModes((prev) => ({
                    ...prev,
                    [change.id]: "edit",
                  }));
                }}
                className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted hover:bg-accent/10 hover:text-accent"
              >
                &#9998; Edit
              </button>
            )}
            {isSingle && (
              <div className="flex border border-border rounded overflow-hidden">
                {change.tool_name !== "create_note" && (
                  <button
                    onClick={() =>
                      setViewModes((prev) => ({
                        ...prev,
                        [change.id]: "diff",
                      }))
                    }
                    className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "diff" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
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
                  className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "preview" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
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
                    className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "edit" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                  >
                    Edit
                  </button>
                )}
              </div>
            )}
            {!isSingle && (
              <span
                className={`text-xs text-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
              >
                &#9662;
              </span>
            )}
          </div>
        </div>

        {/* Expanded content */}
        {isExpanded && (
          <div
            className={
              isSingle ? "flex-1 min-h-0 overflow-y-auto" : "px-4 pb-3"
            }
          >
            {!isSingle && (
              <div className="flex gap-1 mb-2 items-center">
                {change.tool_name !== "create_note" && (
                  <button
                    onClick={() =>
                      setViewModes((prev) => ({
                        ...prev,
                        [change.id]: "diff",
                      }))
                    }
                    className={`text-[11px] py-0.5 px-2.5 border-none rounded cursor-pointer ${mode === "diff" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
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
                  className={`text-[11px] py-0.5 px-2.5 border-none rounded cursor-pointer ${mode === "preview" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
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
                    className={`text-[11px] py-0.5 px-2.5 border-none rounded cursor-pointer ${mode === "edit" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                  >
                    Edit
                  </button>
                )}
                {mode === "edit" && savingIds.has(change.id) && (
                  <span className="text-[10px] text-muted animate-pulse ml-2">
                    Saving...
                  </span>
                )}
              </div>
            )}
            {mode === "diff" && change.tool_name !== "create_note" ? (
              <DiffViewer
                diff={change.diff}
                filePath={filePath}
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
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          {isSingle ? "Review Change" : "Review Changes"}
          {!isSingle && (
            <span className="bg-elevated text-accent text-xs px-2 py-0.5 rounded-full">
              {changes.length}
            </span>
          )}
        </h3>
        {!readOnly && !isSingle && (
          <div className="flex items-center gap-3 text-xs">
            <button
              onClick={() => setAllStatuses("approved")}
              className="bg-transparent border-none text-green font-semibold flex items-center gap-1 cursor-pointer hover:brightness-125"
            >
              <span className="text-sm">&#10003;</span> Approve All
            </button>
            <span className="text-border">|</span>
            <button
              onClick={() => setAllStatuses("rejected")}
              className="bg-transparent border-none text-red font-semibold flex items-center gap-1 cursor-pointer hover:brightness-125"
            >
              <span className="text-sm">&#10005;</span> Reject All
            </button>
          </div>
        )}
      </div>

      {statusError && (
        <p className="text-red text-xs mb-2">
          Failed to update status: {statusError}
        </p>
      )}

      {isSingle ? (
        <div className="flex flex-col gap-3 mb-4 flex-1 min-h-0">
          {changes.map((c) => renderRow(c, false))}
        </div>
      ) : (
        <div className="flex flex-col gap-4 overflow-y-auto mb-4 flex-1 min-h-0">
          {/* To Review section */}
          {pendingChanges.length > 0 && (
            <div className="flex flex-col gap-3">
              {reviewedChanges.length > 0 && (
                <h4 className="text-xs text-muted font-medium m-0 flex items-center gap-2">
                  To Review
                  <span className="bg-elevated text-muted text-[10px] px-1.5 py-0.5 rounded-full">
                    {pendingChanges.length}
                  </span>
                </h4>
              )}
              {pendingChanges.map((c) => renderRow(c, false))}
            </div>
          )}

          {/* Reviewed section */}
          {reviewedChanges.length > 0 && (
            <div className="flex flex-col gap-3">
              <h4 className="text-xs text-muted font-medium m-0 flex items-center gap-2">
                Reviewed
                <span className="bg-elevated text-muted text-[10px] px-1.5 py-0.5 rounded-full">
                  {reviewedChanges.length}
                </span>
              </h4>
              {reviewedChanges.map((c) => renderRow(c, true))}
            </div>
          )}
        </div>
      )}

      {!readOnly && (
        <div className="flex gap-3 pt-4 border-t border-border">
          <button
            onClick={handleApply}
            disabled={applying || approvedCount === 0}
            className="bg-accent text-crust border-none py-2 px-5 rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {applying
              ? "Applying..."
              : isSingle
                ? "Approve"
                : `Apply ${approvedCount} Change${approvedCount !== 1 ? "s" : ""}`}
          </button>
          <button
            onClick={handleReject}
            className="bg-transparent text-red border border-red/30 py-2 px-5 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover:bg-red/5"
            disabled={applying}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
