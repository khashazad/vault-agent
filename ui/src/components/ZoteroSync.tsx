import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  fetchZoteroStatus,
  fetchZoteroPapers,
  fetchZoteroPaperAnnotations,
  fetchZoteroCollections,
  fetchZoteroPapersCacheStatus,
  triggerZoteroPapersRefresh,
  syncZoteroPaper,
  fetchChangesetCost,
} from "../api/client";
import type {
  ZoteroStatus,
  ZoteroPaperSummary,
  ZoteroAnnotationItem,
  ZoteroCollection,
  Changeset,
  TokenUsage,
} from "../types";
import { ErrorAlert } from "./ErrorAlert";
import { formatError } from "../utils";
import { CollectionTree, CollectionTreeSkeleton } from "./CollectionTree";
import { ChangesetReview } from "./ChangesetReview";

type Step = "papers" | "annotations" | "processing";

const PAGE_SIZE = 25;

const COLOR_NAMES: Record<string, string> = {
  "#ffd400": "Yellow",
  "#ff6666": "Red",
  "#5fb236": "Green",
  "#2ea8e5": "Blue",
  "#a28ae5": "Purple",
  "#e56eee": "Magenta",
  "#f19837": "Orange",
  "#aaaaaa": "Gray",
};

function StepIndicator({
  current,
  onNavigate,
}: {
  current: Step;
  onNavigate: (step: Step) => void;
}) {
  const steps: { key: Step; label: string }[] = [
    { key: "papers", label: "Papers" },
    { key: "annotations", label: "Annotations" },
    { key: "processing", label: "Results" },
  ];
  const currentIndex = steps.findIndex((s) => s.key === current);

  return (
    <div className="flex items-center gap-1 text-xs mb-4">
      {steps.map((step, i) => {
        const isCompleted = i < currentIndex;
        const isCurrent = step.key === current;
        return (
          <div key={step.key} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted mx-1">&rarr;</span>}
            <button
              onClick={() => isCompleted && onNavigate(step.key)}
              disabled={!isCompleted}
              className={`px-2 py-0.5 rounded border-none cursor-default ${
                isCurrent
                  ? "bg-accent text-crust font-medium"
                  : isCompleted
                    ? "bg-transparent text-accent !cursor-pointer underline"
                    : "bg-transparent text-muted"
              }`}
            >
              {step.label}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function CostPopover({
  changesetId,
  onClose,
}: {
  changesetId: string;
  onClose: () => void;
}) {
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchChangesetCost(changesetId)
      .then(setUsage)
      .finally(() => setLoading(false));
  }, [changesetId]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute right-0 top-full mt-1 z-10 bg-surface border border-border rounded p-3 shadow-lg min-w-[180px] text-xs"
    >
      {loading ? (
        <span className="text-muted animate-pulse">Loading...</span>
      ) : !usage ? (
        <span className="text-muted">No cost data</span>
      ) : (
        <div className="flex flex-col gap-1.5">
          <div className="flex justify-between">
            <span className="text-muted">Total cost</span>
            <span className="font-medium">
              ${usage.total_cost_usd.toFixed(4)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">Tokens</span>
            <span>
              {formatTokens(usage.input_tokens)} in &middot;{" "}
              {formatTokens(usage.output_tokens)} out
              {(usage.cache_write_tokens > 0 ||
                usage.cache_read_tokens > 0) && (
                <>
                  {" "}
                  &middot;{" "}
                  {formatTokens(
                    usage.cache_write_tokens + usage.cache_read_tokens,
                  )}{" "}
                  cache
                </>
              )}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted">API calls</span>
            <span>{usage.api_calls}</span>
          </div>
          {usage.is_batch && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent self-start">
              Batch (50% off)
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function ZoteroSync() {
  const [status, setStatus] = useState<ZoteroStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Step state
  const [step, setStep] = useState<Step>("papers");

  // Papers step
  const [papers, setPapers] = useState<ZoteroPaperSummary[]>([]);
  const [papersLoading, setPapersLoading] = useState(false);
  const [cacheUpdatedAt, setCacheUpdatedAt] = useState<string | null>(null);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [totalPapers, setTotalPapers] = useState(0);

  // Search + pagination + filters
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(0);
  const [syncStatus, setSyncStatus] = useState<"all" | "synced" | "unsynced">("unsynced");

  // Collections
  const [collections, setCollections] = useState<ZoteroCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [selectedCollectionKey, setSelectedCollectionKey] = useState<
    string | null
  >(null);

  // Annotations step
  const [selectedPaper, setSelectedPaper] =
    useState<ZoteroPaperSummary | null>(null);
  const [annotations, setAnnotations] = useState<ZoteroAnnotationItem[]>([]);
  const [annotationsLoading, setAnnotationsLoading] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<Set<string>>(new Set());

  // Processing step
  const [processing, setProcessing] = useState(false);
  const [resultChangeset, setResultChangeset] = useState<Changeset | null>(
    null,
  );

  const [costPopoverKey, setCostPopoverKey] = useState<string | null>(null);
  const lastCacheUpdatedAtRef = useRef<string | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadPapers = useCallback(
    async (opts?: {
      collectionKey?: string;
      offset?: number;
      search?: string;
      syncStatus?: string;
    }) => {
      setPapersLoading(true);
      setError(null);
      try {
        const res = await fetchZoteroPapers({
          collectionKey: opts?.collectionKey,
          offset: opts?.offset ?? 0,
          limit: PAGE_SIZE,
          search: opts?.search,
          syncStatus: opts?.syncStatus,
        });
        setPapers(res.papers);
        setTotalPapers(res.total);
        setCacheUpdatedAt(res.cache_updated_at);
        lastCacheUpdatedAtRef.current = res.cache_updated_at;
      } catch (err) {
        setError(formatError(err));
      } finally {
        setPapersLoading(false);
      }
    },
    [],
  );

  const loadCollections = useCallback(async () => {
    setCollectionsLoading(true);
    try {
      const res = await fetchZoteroCollections();
      setCollections(res.collections);
    } catch (err) {
      console.warn("Failed to load collections:", err);
    } finally {
      setCollectionsLoading(false);
    }
  }, []);

  // Initial status + collections load
  useEffect(() => {
    fetchZoteroStatus()
      .then((s) => {
        setStatus(s);
        if (s.configured) {
          loadCollections();
        }
      })
      .catch((err) => setError(formatError(err)))
      .finally(() => setLoading(false));
  }, [loadCollections]);

  // Load papers when params change
  useEffect(() => {
    if (!status?.configured || step !== "papers") return;
    loadPapers({
      collectionKey: selectedCollectionKey ?? undefined,
      offset: page * PAGE_SIZE,
      search: debouncedSearch || undefined,
      syncStatus,
    });
  }, [
    status?.configured,
    step,
    selectedCollectionKey,
    page,
    debouncedSearch,
    syncStatus,
    loadPapers,
  ]);

  async function handleRefresh() {
    try {
      await triggerZoteroPapersRefresh();
      setSyncInProgress(true);

      const pollInterval = setInterval(async () => {
        try {
          const cacheStatus = await fetchZoteroPapersCacheStatus();
          if (!cacheStatus.sync_in_progress) {
            clearInterval(pollInterval);
            setSyncInProgress(false);
            if (cacheStatus.cache_updated_at) {
              lastCacheUpdatedAtRef.current = cacheStatus.cache_updated_at;
              setCacheUpdatedAt(cacheStatus.cache_updated_at);
            }
            loadPapers({
              collectionKey: selectedCollectionKey ?? undefined,
              offset: page * PAGE_SIZE,
              search: debouncedSearch || undefined,
              syncStatus,
            });
            loadCollections();
          }
        } catch {
          // Polling failure is non-fatal
        }
      }, 3000);
    } catch (err) {
      setError(formatError(err));
    }
  }

  async function handleSelectPaper(paper: ZoteroPaperSummary) {
    setSelectedPaper(paper);
    setAnnotationsLoading(true);
    setError(null);
    setStep("annotations");
    try {
      const res = await fetchZoteroPaperAnnotations(paper.key);
      setAnnotations(res.annotations);
      setCheckedKeys(new Set(res.annotations.map((a) => a.key)));
    } catch (err) {
      setError(formatError(err));
      setStep("papers");
    } finally {
      setAnnotationsLoading(false);
    }
  }

  function handleSyncStatusChange(s: "all" | "synced" | "unsynced") {
    setSyncStatus(s);
    setPage(0);
  }

  function handleSelectCollection(key: string | null) {
    setSelectedCollectionKey(key);
    setPage(0);
    setSearchQuery("");
    setDebouncedSearch("");
  }

  function handleBackToPapers() {
    setStep("papers");
    setSelectedPaper(null);
    setAnnotations([]);
    setCheckedKeys(new Set());
    setResultChangeset(null);
    setError(null);
  }

  function handleStepNavigate(target: Step) {
    if (target === "papers") {
      handleBackToPapers();
    } else if (target === "annotations" && step === "processing") {
      setStep("annotations");
      setProcessing(false);
      setResultChangeset(null);
      setError(null);
    }
  }

  function toggleAnnotation(key: string) {
    setCheckedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAll() {
    if (checkedKeys.size === annotations.length) {
      setCheckedKeys(new Set());
    } else {
      setCheckedKeys(new Set(annotations.map((a) => a.key)));
    }
  }

  async function handleProcess() {
    if (!selectedPaper) return;
    setStep("processing");
    setProcessing(true);
    setError(null);
    setResultChangeset(null);

    const excluded = annotations
      .filter((a) => !checkedKeys.has(a.key))
      .map((a) => a.key);

    try {
      const changeset = await syncZoteroPaper(
        selectedPaper.key,
        excluded.length > 0 ? excluded : undefined,
      );
      setResultChangeset(changeset);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setProcessing(false);
    }
  }

  // Group annotations by color for display
  const groupedAnnotations = useMemo(() => {
    if (annotations.length === 0) return [];
    const groups: {
      color: string;
      name: string;
      items: ZoteroAnnotationItem[];
    }[] = [];
    const sorted = [...annotations].sort((a, b) =>
      (a.color || "").localeCompare(b.color || ""),
    );
    let currentColor = "";
    for (const ann of sorted) {
      if (ann.color !== currentColor) {
        currentColor = ann.color;
        groups.push({
          color: currentColor,
          name: COLOR_NAMES[currentColor.toLowerCase()] || "Other",
          items: [],
        });
      }
      groups[groups.length - 1].items.push(ann);
    }
    return groups;
  }, [annotations]);

  const totalPages = Math.ceil(totalPapers / PAGE_SIZE);

  if (loading) {
    return <div className="text-muted text-sm">Loading Zotero status...</div>;
  }

  if (status && !status.configured) {
    return (
      <div className="bg-surface border border-border rounded p-5 flex flex-col gap-3">
        <h2 className="text-base font-semibold m-0">Zotero Integration</h2>
        <p className="text-sm text-muted m-0">
          Zotero is not configured. Set <code>ZOTERO_API_KEY</code> and{" "}
          <code>ZOTERO_LIBRARY_ID</code> in your <code>.env</code> file to
          enable syncing.
        </p>
        <p className="text-xs text-muted m-0">
          Get your API key at{" "}
          <a
            href="https://www.zotero.org/settings/keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent underline"
          >
            zotero.org/settings/keys
          </a>
        </p>
      </div>
    );
  }

  // --- Papers step ---
  if (step === "papers") {
    const isInitialSync = !cacheUpdatedAt && papers.length === 0;

    return (
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold m-0">Zotero Library</h2>
            {syncInProgress && (
              <span className="text-xs text-muted animate-pulse">
                Syncing...
              </span>
            )}
          </div>
          <button
            onClick={handleRefresh}
            disabled={syncInProgress}
            className="text-xs text-accent bg-transparent border border-accent rounded px-3 py-1 cursor-pointer disabled:opacity-50"
          >
            {syncInProgress ? "Syncing..." : "Sync with Zotero"}
          </button>
        </div>

        {error && <ErrorAlert message={error} />}

        {isInitialSync ? (
          <div className="bg-surface border border-border rounded p-6 flex flex-col items-center gap-3">
            <div className="text-muted text-sm animate-pulse">
              Syncing with Zotero...
            </div>
            <div className="text-xs text-muted">
              Papers will appear here once the initial sync completes.
            </div>
          </div>
        ) : (
          <div className="flex gap-4 max-h-[calc(100vh-200px)]">
            {/* Collections sidebar */}
            {(collectionsLoading || collections.length > 0) && (
              <div className="w-[220px] flex-shrink-0 overflow-y-auto border-r border-border pr-3">
                {collectionsLoading ? (
                  <CollectionTreeSkeleton />
                ) : (
                  <CollectionTree
                    collections={collections}
                    selectedKey={selectedCollectionKey}
                    onSelect={handleSelectCollection}
                  />
                )}
              </div>
            )}

            {/* Papers list */}
            <div className="flex-1 overflow-y-auto flex flex-col gap-3">
              {/* Search input */}
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by title or author..."
                className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted outline-none focus:border-accent"
              />

              {/* Sync status filter */}
              <div className="flex gap-2">
                {(["all", "synced", "unsynced"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSyncStatusChange(s)}
                    className={
                      syncStatus === s
                        ? "px-3 py-1.5 text-xs font-medium rounded bg-accent/15 text-accent"
                        : "px-3 py-1.5 text-xs font-medium rounded bg-surface text-muted border border-border"
                    }
                  >
                    {s === "all" ? "All" : s === "synced" ? "Synced" : "Not Synced"}
                  </button>
                ))}
              </div>

              {papersLoading && papers.length === 0 ? (
                <div className="text-muted text-sm">Loading papers...</div>
              ) : papers.length === 0 ? (
                <div className="text-muted text-sm">
                  {debouncedSearch
                    ? "No papers match your search."
                    : "No papers found."}
                </div>
              ) : (
                <>
                  <div className="flex flex-col gap-2">
                    {papers.map((paper) => (
                      <button
                        key={paper.key}
                        onClick={() => handleSelectPaper(paper)}
                        className="bg-surface border border-border rounded p-4 text-left cursor-pointer hover:border-accent transition-colors w-full"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex flex-col gap-1 min-w-0">
                            <span className="text-sm font-medium truncate">
                              {paper.title || "Untitled"}
                            </span>
                            <span className="text-xs text-muted truncate">
                              {paper.authors.length > 0
                                ? paper.authors.join(", ")
                                : "Unknown author"}
                              {paper.year ? ` (${paper.year})` : ""}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0 relative">
                            {paper.annotation_count != null &&
                              paper.annotation_count > 0 && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent">
                                  {paper.annotation_count}
                                </span>
                              )}
                            {paper.changeset_id && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setCostPopoverKey(
                                    costPopoverKey === paper.key
                                      ? null
                                      : paper.key,
                                  );
                                }}
                                className="text-[10px] px-1.5 py-0.5 rounded bg-surface border border-border text-muted hover:text-accent hover:border-accent cursor-pointer"
                                title="View LLM cost"
                              >
                                $
                              </button>
                            )}
                            {costPopoverKey === paper.key &&
                              paper.changeset_id && (
                                <CostPopover
                                  changesetId={paper.changeset_id}
                                  onClose={() => setCostPopoverKey(null)}
                                />
                              )}
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${
                                paper.last_synced
                                  ? "bg-green-bg text-green"
                                  : "bg-surface text-muted border border-border"
                              }`}
                            >
                              {paper.last_synced
                                ? `Synced ${new Date(paper.last_synced).toLocaleDateString()}`
                                : "Never synced"}
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
                        {Math.min((page + 1) * PAGE_SIZE, totalPapers)} of{" "}
                        {totalPapers}
                      </span>
                      <button
                        onClick={() => setPage((p) => p + 1)}
                        disabled={(page + 1) * PAGE_SIZE >= totalPapers}
                        className="text-xs text-accent bg-transparent border border-border rounded px-3 py-1 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Next &rarr;
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  // --- Annotations step ---
  if (step === "annotations") {
    const checkedCount = checkedKeys.size;

    return (
      <div className="flex flex-col gap-4">
        <StepIndicator current="annotations" onNavigate={handleStepNavigate} />

        <div className="flex items-center gap-3">
          <button
            onClick={handleBackToPapers}
            className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
            title="Back to papers"
          >
            &larr;
          </button>
          <div className="flex flex-col gap-0.5 min-w-0">
            <h2 className="text-base font-semibold m-0 truncate">
              {selectedPaper?.title || "Untitled"}
            </h2>
            <span className="text-xs text-muted">
              {selectedPaper?.authors.join(", ")}
              {selectedPaper?.year ? ` (${selectedPaper.year})` : ""}
            </span>
          </div>
        </div>

        {error && <ErrorAlert message={error} />}

        {annotationsLoading ? (
          <div className="text-muted text-sm">Loading annotations...</div>
        ) : annotations.length === 0 ? (
          <div className="text-muted text-sm">
            No annotations found for this paper.
          </div>
        ) : (
          <>
            <div className="flex flex-col gap-3 max-h-[calc(100vh-340px)] overflow-y-auto pb-16">
              {groupedAnnotations.map((group) => (
                <div key={group.color} className="flex flex-col gap-2">
                  {groupedAnnotations.length > 1 && (
                    <div className="flex items-center gap-2 text-xs text-muted pt-1">
                      <span
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: group.color || "#888" }}
                      />
                      <span>
                        {group.name} ({group.items.length})
                      </span>
                    </div>
                  )}
                  {group.items.map((ann) => (
                    <label
                      key={ann.key}
                      className="bg-surface border border-border rounded p-3 flex gap-3 cursor-pointer hover:border-accent transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={checkedKeys.has(ann.key)}
                        onChange={() => toggleAnnotation(ann.key)}
                        className="accent-accent mt-1 flex-shrink-0"
                      />
                      <div className="flex flex-col gap-1.5 min-w-0">
                        {ann.text && (
                          <blockquote
                            className="m-0 pl-3 text-sm"
                            style={{
                              borderLeft: `3px solid ${ann.color || "#888"}`,
                            }}
                          >
                            {ann.text}
                          </blockquote>
                        )}
                        {ann.comment && (
                          <span className="text-xs italic text-muted">
                            {ann.comment}
                          </span>
                        )}
                        <span className="text-[10px] text-muted">
                          {ann.page_label ? `p. ${ann.page_label}` : ""}
                          {ann.page_label && ann.date_added ? " · " : ""}
                          {ann.date_added
                            ? new Date(ann.date_added).toLocaleDateString()
                            : ""}
                        </span>
                      </div>
                    </label>
                  ))}
                </div>
              ))}
            </div>

            {/* Sticky action bar */}
            <div className="sticky bottom-0 bg-bg border-t border-border py-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xs text-muted">
                  {checkedCount} of {annotations.length} selected
                </span>
                <button
                  onClick={toggleAll}
                  className="text-xs text-accent bg-transparent border-none cursor-pointer p-0 underline"
                >
                  {checkedKeys.size === annotations.length
                    ? "Deselect All"
                    : "Select All"}
                </button>
              </div>
              <button
                onClick={handleProcess}
                disabled={checkedCount === 0}
                className="bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Process {checkedCount} annotation
                {checkedCount !== 1 ? "s" : ""}
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  // --- Processing step ---
  return (
    <div className="flex flex-col gap-4">
      <StepIndicator current="processing" onNavigate={handleStepNavigate} />

      <div className="flex items-center gap-3">
        <button
          onClick={handleBackToPapers}
          className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
          title="Back to papers"
          disabled={processing}
        >
          &larr;
        </button>
        <h2 className="text-base font-semibold m-0">
          {processing ? "Processing..." : "Results"}
        </h2>
      </div>

      {error && <ErrorAlert message={error} />}

      {processing && (
        <div className="bg-surface border border-border rounded p-6 flex flex-col items-center gap-3">
          <div className="text-muted text-sm animate-pulse">
            Running agent on annotations from &ldquo;{selectedPaper?.title}
            &rdquo;...
          </div>
          <div className="text-xs text-muted">This may take a moment.</div>
        </div>
      )}

      {!processing && resultChangeset && (
        <div className="flex flex-col gap-3">
          {/* Routing summary */}
          {resultChangeset.routing && (
            <div className="bg-surface border border-border rounded p-3 text-sm">
              <span className="text-muted">Route:</span>{" "}
              <span className="font-medium capitalize">
                {resultChangeset.routing.action}
              </span>
              {resultChangeset.routing.target_path && (
                <span className="font-mono text-xs ml-2">
                  &rarr; {resultChangeset.routing.target_path}
                </span>
              )}
              <span className="text-muted ml-2">
                ({resultChangeset.changes.length} change
                {resultChangeset.changes.length !== 1 ? "s" : ""})
              </span>
            </div>
          )}

          <ChangesetReview
            changesetId={resultChangeset.id}
            initialChanges={resultChangeset.changes}
            onDone={handleBackToPapers}
          />

        </div>
      )}

      {!processing && !resultChangeset && !error && (
        <div className="text-muted text-sm">No results yet.</div>
      )}
    </div>
  );
}
