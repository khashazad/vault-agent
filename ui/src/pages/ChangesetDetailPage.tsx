import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router";
import type { Changeset, TokenUsage, PassageAnnotation } from "../types";
import {
  fetchChangeset,
  fetchChangesetCost,
  requestChanges,
  regenerateChangeset,
  deleteChangeset,
} from "../api/client";
import { formatError, formatTokens } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { ChangesetReview } from "../components/ChangesetReview";
import {
  AnnotationFeedback,
  formatAnnotations,
} from "../components/AnnotationFeedback";
import { StatusBadge } from "../components/StatusBadge";
import { Skeleton } from "../components/Skeleton";
import { useClickOutside } from "../hooks/useClickOutside";

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

export function ChangesetDetailPage() {
  const { changesetId } = useParams<{ changesetId: string }>();
  const navigate = useNavigate();

  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<Changeset | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [annotations, setAnnotations] = useState<PassageAnnotation[]>([]);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [splitPercent, setSplitPercent] = useState(72);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const loadDetail = useCallback(async (id: string) => {
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

  useEffect(() => {
    if (changesetId) loadDetail(changesetId);
  }, [changesetId, loadDetail]);

  function backToList() {
    navigate("/changesets");
  }

  const handleRequestChanges = useCallback(async () => {
    if (!changesetId || annotations.length === 0) return;
    setSubmittingFeedback(true);
    setError(null);
    try {
      await requestChanges(changesetId, formatAnnotations(annotations));
      const cs = await fetchChangeset(changesetId);
      setDetail(cs);
      setAnnotations([]);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmittingFeedback(false);
    }
  }, [changesetId, annotations]);

  const handleRegenerate = useCallback(async () => {
    if (!changesetId) return;
    setRegenerating(true);
    setError(null);
    try {
      const newCs = await regenerateChangeset(changesetId);
      navigate(`/changesets/${newCs.id}`);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setRegenerating(false);
    }
  }, [changesetId, navigate]);

  const handleDelete = useCallback(async () => {
    if (!changesetId) return;
    setConfirmDelete(false);
    setDeleting(true);
    setError(null);
    try {
      await deleteChangeset(changesetId);
      backToList();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setDeleting(false);
    }
  }, [changesetId]);

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
                onClick={() => setConfirmDelete(true)}
                disabled={deleting}
                className="text-xs text-red bg-transparent border border-red/30 rounded px-3 py-1 cursor-pointer hover:bg-red/10 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="detail-delete"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
              {confirmDelete && (
                <DeleteConfirmPopover
                  onConfirm={handleDelete}
                  onCancel={() => setConfirmDelete(false)}
                />
              )}
            </div>
          </div>

          {detail.parent_changeset_id && (
            <div className="text-xs text-muted">
              Regenerated from{" "}
              <button
                onClick={() =>
                  navigate(`/changesets/${detail.parent_changeset_id}`)
                }
                className="text-accent underline bg-transparent border-none cursor-pointer p-0 text-xs"
              >
                {detail.parent_changeset_id.slice(0, 8)}...
              </button>
            </div>
          )}

          {detail.feedback && detail.status === "revision_requested" && (
            <div className="bg-surface border border-border rounded p-3">
              <span className="text-xs text-muted block mb-1">Feedback:</span>
              <p className="text-sm m-0">{detail.feedback}</p>
            </div>
          )}

          <div
            ref={containerRef}
            className="flex items-stretch w-full flex-1 min-h-0"
          >
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
