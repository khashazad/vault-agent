import { useState, useEffect, useCallback } from "react";
import type { ChangesetSummary, Changeset, TokenUsage } from "../types";
import {
  fetchChangesets,
  fetchChangeset,
  fetchChangesetCost,
  requestChanges,
  regenerateChangeset,
} from "../api/client";
import { formatError } from "../utils";
import { ErrorAlert } from "./ErrorAlert";
import { ChangesetReview } from "./ChangesetReview";

type View = "list" | "detail";
type StatusFilter = "all" | "pending" | "applied" | "rejected" | "revision_requested";

const PAGE_SIZE = 25;

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-accent/15 text-accent",
  applied: "bg-green-bg text-green",
  rejected: "bg-red-bg text-red",
  partially_applied: "bg-accent/15 text-accent",
  skipped: "bg-surface text-muted border border-border",
  revision_requested: "bg-accent/15 text-yellow",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_COLORS[status] ?? "bg-surface text-muted"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
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
  const [feedbackText, setFeedbackText] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

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
    setFeedbackText("");
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
    setFeedbackText("");
  }, []);

  const handleRequestChanges = useCallback(async () => {
    if (!selectedId || !feedbackText.trim()) return;
    setSubmittingFeedback(true);
    setError(null);
    try {
      await requestChanges(selectedId, feedbackText.trim());
      // Reload detail
      const cs = await fetchChangeset(selectedId);
      setDetail(cs);
      setFeedbackText("");
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmittingFeedback(false);
    }
  }, [selectedId, feedbackText]);

  const handleRegenerate = useCallback(async () => {
    if (!selectedId) return;
    setRegenerating(true);
    setError(null);
    try {
      const newCs = await regenerateChangeset(selectedId);
      // Navigate to the new changeset
      openDetail(newCs.id);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setRegenerating(false);
    }
  }, [selectedId, openDetail]);

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
          <div className="text-muted text-sm">Loading changesets...</div>
        ) : summaries.length === 0 ? (
          <div className="text-muted text-sm">No changesets found.</div>
        ) : (
          <>
            <div className="flex flex-col gap-2">
              {summaries.map((cs) => (
                <button
                  key={cs.id}
                  onClick={() => openDetail(cs.id)}
                  className="bg-surface border border-border rounded p-4 text-left cursor-pointer hover:border-accent transition-colors w-full"
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
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={() => setPage((p) => p - 1)}
                  disabled={page === 0}
                  className="text-xs text-accent bg-transparent border border-border rounded px-3 py-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  &larr; Previous
                </button>
                <span className="text-xs text-muted">
                  {page * PAGE_SIZE + 1}&ndash;
                  {Math.min((page + 1) * PAGE_SIZE, total)} of {total}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={(page + 1) * PAGE_SIZE >= total}
                  className="text-xs text-accent bg-transparent border border-border rounded px-3 py-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next &rarr;
                </button>
              </div>
            )}
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
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <button
          onClick={backToList}
          className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
          title="Back to list"
        >
          &larr;
        </button>
        <h2 className="text-base font-semibold m-0">Changeset Detail</h2>
      </div>

      {error && <ErrorAlert message={error} />}

      {detailLoading ? (
        <div className="text-muted text-sm">Loading changeset...</div>
      ) : detail ? (
        <div className="flex flex-col gap-4">
          {/* Metadata bar */}
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
            {usage && <CostDisplay usage={usage} />}
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

          {/* Changeset review */}
          <ChangesetReview
            changesetId={detail.id}
            initialChanges={detail.changes}
            onDone={backToList}
            readOnly={!isInteractive}
          />

          {/* Feedback section */}
          {isInteractive && (
            <div className="bg-surface border border-border rounded p-4 flex flex-col gap-3">
              <h4 className="text-sm font-medium m-0">Request Changes</h4>
              <textarea
                className="w-full h-24 bg-bg border border-border rounded p-3 text-sm text-foreground resize-y outline-none focus:border-accent"
                placeholder="Describe what should be different..."
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
              />
              <button
                onClick={handleRequestChanges}
                disabled={submittingFeedback || !feedbackText.trim()}
                className="self-start bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submittingFeedback ? "Submitting..." : "Request Changes"}
              </button>
            </div>
          )}

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
      ) : (
        <div className="text-muted text-sm">Changeset not found.</div>
      )}
    </div>
  );
}
