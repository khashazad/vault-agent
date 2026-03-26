import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router";
import type {
  Changeset,
  PassageAnnotation,
  ProposedChange,
  TokenUsage,
} from "../types";
import {
  fetchChangeset,
  fetchChangesetCost,
  requestChanges,
  regenerateChangeset,
  deleteChangeset,
  convergeClawdy,
} from "../api/client";
import { formatError, formatTokens } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { ChangesetReview } from "../components/ChangesetReview";
import { DiffViewer } from "../components/DiffViewer";
import { FileExplorer } from "../components/FileExplorer";
import { MarkdownPreview } from "../components/MarkdownPreview";
import {
  AnnotationFeedback,
  formatAnnotations,
} from "../components/AnnotationFeedback";
import { StatusBadge } from "../components/StatusBadge";
import { Skeleton } from "../components/Skeleton";
import { useChangesetActions } from "../hooks/useChangesetActions";
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

function changeBadgeLabel(toolName: string) {
  if (toolName === "create_note") return "NEW";
  if (toolName === "delete_note") return "DEL";
  return "MOD";
}

function changeBadgeClass(toolName: string) {
  if (toolName === "create_note") return "bg-green/15 text-green";
  if (toolName === "delete_note") return "bg-red/15 text-red";
  return "bg-yellow/15 text-yellow";
}

function formatChangeTimestamp(detail: Changeset) {
  const created = new Date(detail.created_at).toLocaleString();
  if (!detail.updated_at || detail.updated_at === detail.created_at) {
    return created;
  }
  return `Created ${created}, updated ${new Date(detail.updated_at).toLocaleString()}`;
}

function defaultViewMode(change: ProposedChange) {
  return change.tool_name === "create_note" ? "preview" : "diff";
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
  const [converging, setConverging] = useState(false);
  const [splitPercent, setSplitPercent] = useState(72);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
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

  useEffect(() => {
    if (!detail?.changes.length) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) => {
      if (current && detail.changes.some((change) => change.id === current)) {
        return current;
      }
      return detail.changes[0].id;
    });
  }, [detail]);

  function backToList() {
    if (detailLoading) return;
    if (detail?.source_type === "clawdy") {
      navigate("/clawdy");
    } else {
      navigate("/changesets");
    }
  }

  const changesetActions = useChangesetActions({
    changesetId: detail?.id ?? "",
    initialChanges: detail?.changes ?? [],
    sourceType: detail?.source_type ?? "web",
    onDone: backToList,
  });

  const handleConverge = useCallback(async () => {
    if (!changesetId) return;
    setConverging(true);
    setError(null);
    try {
      await convergeClawdy(changesetId);
      const cs = await fetchChangeset(changesetId);
      setDetail(cs);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setConverging(false);
    }
  }, [changesetId]);

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
  const isClawdy = detail?.source_type === "clawdy";
  const allResolved = detail?.changes.every(
    (c) => c.status === "applied" || c.status === "rejected",
  );
  const showConverge =
    isClawdy &&
    allResolved &&
    detail?.status !== "applied" &&
    detail?.status !== "rejected";
  const isMultiChange = (detail?.changes.length ?? 0) > 1;
  const selectedChange =
    changesetActions.changes.find((change) => change.id === selectedId) ??
    changesetActions.changes[0] ??
    null;
  const selectedMode = selectedChange
    ? changesetActions.viewModes[selectedChange.id] ??
      defaultViewMode(selectedChange)
    : "preview";
  const multiApprovedCount = changesetActions.changes.filter(
    (change) => change.status === "approved",
  ).length;

  return (
    <div className="flex flex-col gap-4 flex-1 min-h-0 py-6 px-8">
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
              {formatChangeTimestamp(detail)}
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
            {showConverge && (
              <button
                onClick={handleConverge}
                disabled={converging}
                className="text-xs bg-green/15 text-green border border-green/30 rounded px-3 py-1 cursor-pointer hover:bg-green/25 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {converging ? "Syncing..." : "Finalize & Sync"}
              </button>
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
                Previous version
              </button>
            </div>
          )}

          {detail.feedback && detail.status === "revision_requested" && (
            <div className="bg-surface border border-border rounded p-3">
              <span className="text-xs text-muted block mb-1">Feedback:</span>
              <p className="text-sm m-0">{detail.feedback}</p>
            </div>
          )}

          {isMultiChange ? (
            <div className="flex flex-1 min-h-0 gap-4">
              <FileExplorer
                changes={changesetActions.changes}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />

              <div className="flex min-w-0 flex-1 flex-col gap-4">
                {changesetActions.statusError && (
                  <ErrorAlert message={changesetActions.statusError} />
                )}

                {changesetActions.result ? (
                  <div className="bg-surface border border-border rounded-xl p-5 flex flex-col items-center gap-3">
                    {changesetActions.result.applied.length > 0 && (
                      <h3 className="text-sm font-semibold m-0">
                        {changesetActions.result.applied.length} change
                        {changesetActions.result.applied.length !== 1
                          ? "s"
                          : ""}{" "}
                        written to vault
                      </h3>
                    )}
                    {changesetActions.result.failed.length > 0 && (
                      <div className="text-center text-red text-sm">
                        {changesetActions.result.failed.map((failure) => (
                          <p key={failure.id} className="m-0">
                            {failure.error}
                          </p>
                        ))}
                      </div>
                    )}
                    <button
                      onClick={backToList}
                      className="bg-accent text-crust border-none py-2 px-5 rounded text-sm"
                    >
                      Back to Changesets
                    </button>
                  </div>
                ) : selectedChange ? (
                  <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-border bg-surface overflow-hidden">
                    <div className="border-b border-border px-4 py-3 flex flex-wrap items-center gap-3">
                      <span className="font-mono text-sm min-w-0 flex-1 truncate">
                        {String(selectedChange.input.path)}
                      </span>
                      <span
                        className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${changeBadgeClass(selectedChange.tool_name)}`}
                      >
                        {changeBadgeLabel(selectedChange.tool_name)}
                      </span>
                      {isInteractive && (
                        <>
                          {selectedChange.status === "pending" ? (
                            <>
                              <button
                                onClick={() =>
                                  changesetActions.setChangeStatus(
                                    selectedChange.id,
                                    "approved",
                                  )
                                }
                                className="text-xs bg-green/15 text-green border border-green/30 rounded px-3 py-1 cursor-pointer"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() =>
                                  changesetActions.setChangeStatus(
                                    selectedChange.id,
                                    "rejected",
                                  )
                                }
                                className="text-xs bg-red/15 text-red border border-red/30 rounded px-3 py-1 cursor-pointer"
                              >
                                Reject
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() =>
                                changesetActions.setChangeStatus(
                                  selectedChange.id,
                                  "pending",
                                )
                              }
                              className="text-xs bg-elevated text-muted border border-border rounded px-3 py-1 cursor-pointer"
                            >
                              Undo
                            </button>
                          )}
                        </>
                      )}
                      <div className="flex border border-border rounded overflow-hidden">
                        {selectedChange.tool_name !== "create_note" && (
                          <button
                            onClick={() =>
                              changesetActions.setViewMode(
                                selectedChange.id,
                                "diff",
                              )
                            }
                            className={`text-[11px] py-1 px-3 border-none cursor-pointer ${
                              selectedMode === "diff"
                                ? "bg-accent text-crust"
                                : "bg-elevated text-muted"
                            }`}
                          >
                            Diff
                          </button>
                        )}
                        <button
                          onClick={() =>
                            changesetActions.setViewMode(
                              selectedChange.id,
                              "preview",
                            )
                          }
                          className={`text-[11px] py-1 px-3 border-none cursor-pointer ${
                            selectedMode === "preview"
                              ? "bg-accent text-crust"
                              : "bg-elevated text-muted"
                          }`}
                        >
                          Preview
                        </button>
                        {isInteractive && (
                          <button
                            onClick={() =>
                              changesetActions.setViewMode(
                                selectedChange.id,
                                "edit",
                              )
                            }
                            className={`text-[11px] py-1 px-3 border-none cursor-pointer ${
                              selectedMode === "edit"
                                ? "bg-accent text-crust"
                                : "bg-elevated text-muted"
                            }`}
                          >
                            Edit
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="flex-1 min-h-0 overflow-y-auto p-4">
                      {selectedMode === "diff" &&
                      selectedChange.tool_name !== "create_note" ? (
                        <DiffViewer
                          diff={selectedChange.diff}
                          filePath={String(selectedChange.input.path)}
                          isNew={false}
                          originalContent={selectedChange.original_content}
                          proposedContent={selectedChange.proposed_content}
                        />
                      ) : selectedMode === "edit" && isInteractive ? (
                        <div className="flex flex-col gap-2 h-full">
                          {changesetActions.savingIds.has(selectedChange.id) && (
                            <span className="text-xs text-muted animate-pulse">
                              Saving...
                            </span>
                          )}
                          <textarea
                            className="w-full min-h-[420px] bg-bg border border-border rounded p-3 text-sm text-foreground font-mono resize-y outline-none focus:border-accent"
                            value={
                              changesetActions.editBuffers[selectedChange.id] ??
                              selectedChange.proposed_content
                            }
                            onChange={(event) =>
                              changesetActions.handleEditChange(
                                selectedChange.id,
                                event.target.value,
                              )
                            }
                          />
                        </div>
                      ) : (
                        <MarkdownPreview content={selectedChange.proposed_content} />
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="bg-surface border border-border rounded-xl p-5 text-sm text-muted">
                    No change selected.
                  </div>
                )}

                {isInteractive && !changesetActions.result && (
                  <div className="bg-surface border border-border rounded-xl overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setFeedbackOpen((open) => !open)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-transparent border-none text-left cursor-pointer"
                    >
                      <span className="text-sm font-medium">
                        Feedback & Actions
                      </span>
                      <span className="text-xs text-muted">
                        {feedbackOpen ? "Hide" : "Show"}
                      </span>
                    </button>

                    {feedbackOpen && (
                      <div className="border-t border-border p-4 flex flex-col gap-4">
                        <AnnotationFeedback
                          annotations={annotations}
                          onAdd={(annotation) =>
                            setAnnotations((prev) => [...prev, annotation])
                          }
                          onRemove={(id) =>
                            setAnnotations((prev) =>
                              prev.filter((annotation) => annotation.id !== id),
                            )
                          }
                          onSubmit={handleRequestChanges}
                          submitting={submittingFeedback}
                        />

                        <div className="flex flex-wrap items-center gap-3">
                          <button
                            onClick={() =>
                              changesetActions.setAllStatuses("approved")
                            }
                            className="bg-transparent border border-green/30 text-green py-2 px-4 rounded text-sm cursor-pointer"
                          >
                            Approve All
                          </button>
                          <button
                            onClick={() =>
                              changesetActions.setAllStatuses("rejected")
                            }
                            className="bg-transparent border border-red/30 text-red py-2 px-4 rounded text-sm cursor-pointer"
                          >
                            Reject All
                          </button>
                          <button
                            onClick={changesetActions.handleApply}
                            disabled={
                              changesetActions.applying || multiApprovedCount === 0
                            }
                            className="bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                          >
                            {changesetActions.applying
                              ? "Applying..."
                              : `Apply ${multiApprovedCount} Change${
                                  multiApprovedCount !== 1 ? "s" : ""
                                }`}
                          </button>
                          <button
                            onClick={changesetActions.handleReject}
                            disabled={changesetActions.applying}
                            className="bg-transparent text-red border border-red/30 py-2 px-5 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover:bg-red/5"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div ref={containerRef} className="flex flex-1 min-h-0 w-full">
              <div
                className="flex flex-col gap-4 min-w-0 min-h-0"
                style={{ width: isInteractive ? `${splitPercent}%` : "100%" }}
              >
                <ChangesetReview
                  changesetId={detail.id}
                  initialChanges={detail.changes}
                  onDone={backToList}
                  readOnly={!isInteractive}
                  sourceType={detail.source_type}
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
                    className="w-2 mx-3 self-stretch cursor-col-resize rounded-full bg-border hover:bg-accent transition-colors flex-shrink-0 relative flex flex-col items-center justify-center gap-0.5"
                  >
                    <span className="block w-1 h-1 rounded-full bg-muted/50" />
                    <span className="block w-1 h-1 rounded-full bg-muted/50" />
                    <span className="block w-1 h-1 rounded-full bg-muted/50" />
                  </div>
                  <div
                    className="min-w-0 overflow-y-auto flex-shrink-0 pl-2"
                    style={{ width: `${100 - splitPercent}%` }}
                  >
                    <AnnotationFeedback
                      annotations={annotations}
                      onAdd={(a) => setAnnotations((prev) => [...prev, a])}
                      onRemove={(id) =>
                        setAnnotations((prev) =>
                          prev.filter((a) => a.id !== id),
                        )
                      }
                      onSubmit={handleRequestChanges}
                      submitting={submittingFeedback}
                    />
                  </div>
                </>
              )}
            </div>
          )}

          {showRegenerate && isMultiChange && (
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
