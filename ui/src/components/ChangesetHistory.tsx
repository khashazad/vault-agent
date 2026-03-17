import { useState, useEffect, useCallback, useRef } from "react";
import type {
  ChangesetSummary,
  Changeset,
  TokenUsage,
  PassageAnnotation,
} from "../types";
import {
  fetchChangesets,
  fetchChangeset,
  fetchChangesetCost,
  requestChanges,
  regenerateChangeset,
  deleteChangeset,
} from "../api/client";
import { formatError, formatTokens } from "../utils";
import { ErrorAlert } from "./ErrorAlert";
import { ChangesetReview } from "./ChangesetReview";
import { AnnotationFeedback, formatAnnotations } from "./AnnotationFeedback";
import { StatusBadge } from "./StatusBadge";
import { Pagination } from "./Pagination";
import { Skeleton } from "./Skeleton";
import { useClickOutside } from "../hooks/useClickOutside";

type View = "list" | "detail";
type StatusFilter =
  | "all"
  | "pending"
  | "applied"
  | "rejected"
  | "revision_requested";

const PAGE_SIZE = 25;

function TrashIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5.5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0zm3 .5a.5.5 0 0 1-.5-.5.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6a.5.5 0 0 1 .5-.5" />
      <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1 0-2H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1M4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM6 2h4a.5.5 0 0 0-.5-.5h-3A.5.5 0 0 0 6 2" />
    </svg>
  );
}

function DeleteConfirmPopover({
  onConfirm,
  onCancel,
}: {
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, onCancel);

  return (
    <div
      ref={ref}
      data-testid="delete-confirm-popover"
      className="absolute right-0 top-full mt-1 z-10 bg-surface border border-border rounded p-3 shadow-lg min-w-[200px]"
    >
      <p className="text-xs text-muted m-0 mb-2">
        Permanently delete this changeset?
      </p>
      <div className="flex gap-2 justify-end">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCancel();
          }}
          className="text-xs px-3 py-1 rounded bg-transparent border border-border text-muted cursor-pointer hover:text-foreground"
        >
          Cancel
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onConfirm();
          }}
          data-testid="confirm-delete-btn"
          className="text-xs px-3 py-1 rounded bg-red/15 border border-red/30 text-red cursor-pointer hover:bg-red/25"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function CostDisplay({ usage }: { usage: TokenUsage }) {
  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex justify-between gap-4">
        <span className="text-muted">Cost</span>
        <span className="font-medium">${usage.total_cost_usd.toFixed(4)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-muted">Tokens</span>
        <span>
          {formatTokens(usage.input_tokens)} in &middot;{" "}
          {formatTokens(usage.output_tokens)} out
        </span>
      </div>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded p-4 flex flex-col gap-2"
        >
          <div className="flex items-center gap-2">
            <Skeleton h="h-3" w="w-20" />
            <Skeleton h="h-4" w="w-16" className="rounded-full" />
          </div>
          <Skeleton h="h-3" w="w-2/5" />
        </div>
      ))}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="bg-surface border border-border rounded p-3 flex gap-3">
        <Skeleton h="h-4" w="w-16" className="rounded-full" />
        <Skeleton h="h-3" w="w-32" />
        <Skeleton h="h-3" w="w-24" className="ml-auto" />
      </div>
      <div className="bg-surface border border-border rounded p-4 flex flex-col gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} h="h-3" w={i % 3 === 0 ? "w-full" : "w-4/5"} />
        ))}
      </div>
    </div>
  );
}

function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <svg
        width="32"
        height="32"
        viewBox="0 0 16 16"
        fill="currentColor"
        className="text-muted/40"
      >
        <path d="M4 .5a.5.5 0 0 0-1 0V1H2a2 2 0 0 0-2 2v1h16V3a2 2 0 0 0-2-2h-1V.5a.5.5 0 0 0-1 0V1H4zM16 14V5H0v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2" />
      </svg>
      <span className="text-sm text-muted">{message}</span>
      {hint && <span className="text-xs text-muted/70">{hint}</span>}
    </div>
  );
}

export function ChangesetHistory() {
  const [view, setView] = useState<View>("list");
  const [error, setError] = useState<string | null>(null);

  // List state
  const [summaries, setSummaries] = useState<ChangesetSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [listLoading, setListLoading] = useState(false);

  // Detail state
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Changeset | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [annotations, setAnnotations] = useState<PassageAnnotation[]>([]);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [splitPercent, setSplitPercent] = useState(72);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadList = useCallback(async () => {
    setListLoading(true);
    setError(null);
    try {
      const res = await fetchChangesets({
        status: statusFilter === "all" ? undefined : statusFilter,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setSummaries(res.changesets);
      setTotal(res.total);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setListLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    if (view === "list") loadList();
  }, [view, loadList]);

  const openDetail = useCallback(async (id: string) => {
    setSelectedId(id);
    setView("detail");
    setDetailLoading(true);
    setError(null);
    setAnnotations([]);
    setUsage(null);
    try {
      const [cs, cost] = await Promise.all([
        fetchChangeset(id),
        fetchChangesetCost(id),
      ]);
      setDetail(cs);
      setUsage(cost);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const backToList = useCallback(() => {
    setView("list");
    setSelectedId(null);
    setDetail(null);
    setUsage(null);
    setAnnotations([]);
  }, []);

  const handleRequestChanges = useCallback(async () => {
    if (!selectedId || annotations.length === 0) return;
    setSubmittingFeedback(true);
    setError(null);
    try {
      await requestChanges(selectedId, formatAnnotations(annotations));
      const cs = await fetchChangeset(selectedId);
      setDetail(cs);
      setAnnotations([]);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmittingFeedback(false);
    }
  }, [selectedId, annotations]);

  const handleRegenerate = useCallback(async () => {
    if (!selectedId) return;
    setRegenerating(true);
    setError(null);
    try {
      const newCs = await regenerateChangeset(selectedId);
      openDetail(newCs.id);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setRegenerating(false);
    }
  }, [selectedId, openDetail]);

  const openDeleteConfirm = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(id);
  }, []);

  const cancelDelete = useCallback(() => {
    setConfirmDeleteId(null);
  }, []);

  const confirmDelete = useCallback(
    async (id: string) => {
      setConfirmDeleteId(null);
      setDeleting(id);
      setError(null);
      try {
        await deleteChangeset(id);
        if (view === "detail") backToList();
        else loadList();
      } catch (err) {
        setError(formatError(err));
      } finally {
        setDeleting(null);
      }
    },
    [view, backToList, loadList],
  );

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(85, Math.max(40, pct)));
    };

    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // --- List view ---
  if (view === "list") {
    return (
      <div className="flex flex-col gap-4">
        <h2 className="text-base font-semibold m-0">Changeset History</h2>

        {error && <ErrorAlert message={error} />}

        {/* Status filter tabs */}
        <div className="flex gap-2">
          {(
            [
              "all",
              "pending",
              "applied",
              "rejected",
              "revision_requested",
            ] as const
          ).map((s) => (
            <button
              key={s}
              onClick={() => {
                setStatusFilter(s);
                setPage(0);
              }}
              className={
                statusFilter === s
                  ? "px-3 py-1.5 text-xs font-medium rounded bg-accent/15 text-accent"
                  : "px-3 py-1.5 text-xs font-medium rounded bg-surface text-muted border border-border"
              }
            >
              {s === "all"
                ? "All"
                : s === "revision_requested"
                  ? "Revision Requested"
                  : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>

        {listLoading && summaries.length === 0 ? (
          <ListSkeleton />
        ) : summaries.length === 0 ? (
          <EmptyState
            message="No changesets found."
            hint="Process some papers to see changesets here"
          />
        ) : (
          <>
            <div className="flex flex-col gap-2">
              {summaries.map((cs) => (
                <div
                  key={cs.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => openDetail(cs.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") openDetail(cs.id);
                  }}
                  className="bg-surface border border-border rounded p-4 text-left cursor-pointer hover:border-accent transition-colors w-full focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex flex-col gap-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-muted truncate">
                          {cs.id.slice(0, 8)}...
                        </span>
                        <StatusBadge status={cs.status} />
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface border border-border text-muted">
                          {cs.source_type}
                        </span>
                      </div>
                      {cs.routing?.target_path && (
                        <span className="text-xs text-muted truncate">
                          {cs.routing.action} &rarr; {cs.routing.target_path}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent">
                        {cs.change_count} change
                        {cs.change_count !== 1 ? "s" : ""}
                      </span>
                      <span className="text-xs text-muted">
                        {new Date(cs.created_at).toLocaleDateString()}
                      </span>
                      <div className="relative">
                        <button
                          onClick={(e) => openDeleteConfirm(cs.id, e)}
                          disabled={deleting === cs.id}
                          className="text-muted hover:text-red bg-transparent border-none cursor-pointer text-sm p-0 leading-none disabled:opacity-50"
                          aria-label="Delete changeset"
                          title="Delete changeset"
                          data-testid={`delete-${cs.id}`}
                        >
                          <TrashIcon />
                        </button>
                        {confirmDeleteId === cs.id && (
                          <DeleteConfirmPopover
                            onConfirm={() => confirmDelete(cs.id)}
                            onCancel={cancelDelete}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <Pagination
              page={page}
              totalPages={totalPages}
              totalItems={total}
              pageSize={PAGE_SIZE}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    );
  }

  // --- Detail view ---
  const isInteractive =
    detail?.status === "pending" || detail?.status === "partially_applied";
  const showRegenerate = detail?.status === "revision_requested";

  return (
    <div className="flex flex-col gap-4 flex-1 min-h-0">
      <div className="flex items-center gap-3">
        <button
          onClick={backToList}
          className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
          aria-label="Back to list"
          title="Back to list"
        >
          &larr;
        </button>
        <h2 className="text-base font-semibold m-0">Changeset Detail</h2>
      </div>

      {error && <ErrorAlert message={error} />}

      {detailLoading ? (
        <DetailSkeleton />
      ) : detail ? (
        <div className="flex flex-col gap-4 flex-1 min-h-0">
          {/* Metadata bar — full width */}
          <div className="bg-surface border border-border rounded p-3 flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge status={detail.status} />
            <span className="text-xs text-muted">
              {new Date(detail.created_at).toLocaleString()}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface border border-border text-muted">
              {detail.source_type}
            </span>
            {detail.routing && (
              <span className="text-xs">
                <span className="text-muted">Route:</span>{" "}
                <span className="font-medium capitalize">
                  {detail.routing.action}
                </span>
                {detail.routing.target_path && (
                  <span className="font-mono text-xs ml-1">
                    &rarr; {detail.routing.target_path}
                  </span>
                )}
              </span>
            )}
            {usage && (
              <div className="ml-auto">
                <CostDisplay usage={usage} />
              </div>
            )}
            <div className="relative">
              <button
                onClick={(e) => openDeleteConfirm(detail.id, e)}
                disabled={deleting === detail.id}
                className="text-xs text-red bg-transparent border border-red/30 rounded px-3 py-1 cursor-pointer hover:bg-red/10 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="detail-delete"
              >
                {deleting === detail.id ? "Deleting..." : "Delete"}
              </button>
              {confirmDeleteId === detail.id && (
                <DeleteConfirmPopover
                  onConfirm={() => confirmDelete(detail.id)}
                  onCancel={cancelDelete}
                />
              )}
            </div>
          </div>

          {/* Parent link */}
          {detail.parent_changeset_id && (
            <div className="text-xs text-muted">
              Regenerated from{" "}
              <button
                onClick={() => openDetail(detail.parent_changeset_id!)}
                className="text-accent underline bg-transparent border-none cursor-pointer p-0 text-xs"
              >
                {detail.parent_changeset_id.slice(0, 8)}...
              </button>
            </div>
          )}

          {/* Stored feedback display */}
          {detail.feedback && detail.status === "revision_requested" && (
            <div className="bg-surface border border-border rounded p-3">
              <span className="text-xs text-muted block mb-1">Feedback:</span>
              <p className="text-sm m-0">{detail.feedback}</p>
            </div>
          )}

          {/* Resizable split: review + annotations */}
          <div
            ref={containerRef}
            className="flex items-stretch w-full flex-1 min-h-0"
          >
            {/* Left: review */}
            <div
              className="flex flex-col gap-4 min-w-0 overflow-auto"
              style={{ width: isInteractive ? `${splitPercent}%` : "100%" }}
            >
              <ChangesetReview
                changesetId={detail.id}
                initialChanges={detail.changes}
                onDone={backToList}
                readOnly={!isInteractive}
              />

              {/* Regenerate section */}
              {showRegenerate && (
                <div className="bg-surface border border-border rounded p-4 flex flex-col gap-3">
                  <h4 className="text-sm font-medium m-0">Regenerate</h4>
                  <p className="text-xs text-muted m-0">
                    Re-run the agent with the feedback above to produce a new
                    changeset.
                  </p>
                  <button
                    onClick={handleRegenerate}
                    disabled={regenerating}
                    className="self-start bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {regenerating ? "Regenerating..." : "Regenerate"}
                  </button>
                </div>
              )}
            </div>

            {/* Drag handle + annotation sidebar */}
            {isInteractive && (
              <>
                <div
                  onMouseDown={onDragStart}
                  className="w-1.5 mx-1 self-stretch cursor-col-resize rounded-full bg-border hover:bg-accent transition-colors flex-shrink-0 relative flex flex-col items-center justify-center gap-0.5"
                >
                  <span className="block w-1 h-1 rounded-full bg-muted/50" />
                  <span className="block w-1 h-1 rounded-full bg-muted/50" />
                  <span className="block w-1 h-1 rounded-full bg-muted/50" />
                </div>
                <div
                  className="min-w-0 overflow-auto sticky top-4 flex-shrink-0"
                  style={{ width: `${100 - splitPercent}%` }}
                >
                  <AnnotationFeedback
                    annotations={annotations}
                    onAdd={(a) => setAnnotations((prev) => [...prev, a])}
                    onRemove={(id) =>
                      setAnnotations((prev) => prev.filter((a) => a.id !== id))
                    }
                    onSubmit={handleRequestChanges}
                    submitting={submittingFeedback}
                  />
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="text-muted text-sm">Changeset not found.</div>
      )}
    </div>
  );
}
