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
import { formatError, formatTokens } from "../utils";
import { CollectionTree, CollectionTreeSkeleton } from "./CollectionTree";
import { ChangesetReview } from "./ChangesetReview";
import { Skeleton } from "./Skeleton";
import { Pagination } from "./Pagination";
import { useClickOutside } from "../hooks/useClickOutside";

type Step = "papers" | "annotations" | "processing";

const PAGE_SIZE = 25;
const POLL_INTERVAL_MS = 3000;
const SEARCH_DEBOUNCE_MS = 300;

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

const PROCESSING_MESSAGES = [
  "Analyzing annotations...",
  "Generating note...",
  "Building diff...",
];

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
              aria-current={isCurrent ? "step" : undefined}
              className={`px-2 py-0.5 rounded border-none ${
                isCurrent
                  ? "bg-accent text-crust font-medium cursor-default"
                  : isCompleted
                    ? "bg-transparent text-accent cursor-pointer underline"
                    : "bg-transparent text-muted cursor-default"
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

function ProcessingSpinner({ paperTitle }: { paperTitle: string }) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIndex((i) => (i + 1) % PROCESSING_MESSAGES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="bg-surface border border-border rounded p-6 flex flex-col items-center gap-3">
      <div className="flex items-center gap-2 text-sm text-muted">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-[pulse-dot_1s_infinite]" />
        {PROCESSING_MESSAGES[msgIndex]}
      </div>
      <div className="text-xs text-muted">
        Processing &ldquo;{paperTitle}&rdquo;
      </div>
    </div>
  );
}

function PaperListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded p-4 flex flex-col gap-2"
        >
          <Skeleton h="h-4" w="w-3/4" />
          <div className="flex gap-2">
            <Skeleton h="h-3" w="w-1/3" />
            <Skeleton h="h-3" w="w-16" />
          </div>
        </div>
      ))}
    </div>
  );
}

function AnnotationListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 4 }, (_, i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded p-3 flex gap-3"
        >
          <Skeleton h="h-4" w="w-4" className="flex-shrink-0 mt-1" />
          <div className="flex flex-col gap-2 flex-1">
            <Skeleton h="h-10" />
            <Skeleton h="h-3" w="w-1/4" />
          </div>
        </div>
      ))}
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
        <path d="M1 3.5A1.5 1.5 0 0 1 2.5 2h3.879a1.5 1.5 0 0 1 1.06.44l1.122 1.12A1.5 1.5 0 0 0 9.62 4H13.5A1.5 1.5 0 0 1 15 5.5v7a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 12.5v-9z" />
      </svg>
      <span className="text-sm text-muted">{message}</span>
      {hint && <span className="text-xs text-muted/70">{hint}</span>}
    </div>
  );
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

  useClickOutside(ref, onClose);

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
          {usage.model === "sonnet" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent self-start">
              Sonnet 4.6
            </span>
          )}
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
  const [syncStatus, setSyncStatus] = useState<"all" | "synced" | "unsynced">(
    "unsynced",
  );

  // Collections
  const [collections, setCollections] = useState<ZoteroCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [selectedCollectionKey, setSelectedCollectionKey] = useState<
    string | null
  >(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Annotations step
  const [selectedPaper, setSelectedPaper] = useState<ZoteroPaperSummary | null>(
    null,
  );
  const [annotations, setAnnotations] = useState<ZoteroAnnotationItem[]>([]);
  const [annotationsLoading, setAnnotationsLoading] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<Set<string>>(new Set());

  // Model selection
  const [model, setModel] = useState<"haiku" | "sonnet">("sonnet");

  // Processing step
  const [processing, setProcessing] = useState(false);
  const [resultChangeset, setResultChangeset] = useState<Changeset | null>(
    null,
  );

  const [costPopoverKey, setCostPopoverKey] = useState<string | null>(null);

  // Polling ref for cleanup
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(0);
    }, SEARCH_DEBOUNCE_MS);
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

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  async function handleRefresh() {
    try {
      await triggerZoteroPapersRefresh();
      setSyncInProgress(true);

      // Clear any existing poll
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
        // Pause polling when tab is hidden
        if (document.hidden) return;

        try {
          const cacheStatus = await fetchZoteroPapersCacheStatus();
          if (!cacheStatus.sync_in_progress) {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            setSyncInProgress(false);
            if (cacheStatus.cache_updated_at) {
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
      }, POLL_INTERVAL_MS);
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
        model,
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
  const showSidebar = collectionsLoading || collections.length > 0;

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
          <div className="flex gap-4 flex-1 min-h-0">
            {/* Collections sidebar */}
            {showSidebar && (
              <div className="relative flex-shrink-0">
                {sidebarCollapsed ? (
                  <button
                    onClick={() => setSidebarCollapsed(false)}
                    className="bg-surface border border-border rounded p-1 text-muted hover:text-foreground cursor-pointer"
                    aria-label="Expand sidebar"
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 16 16"
                      fill="currentColor"
                    >
                      <path d="M6 3l5 5-5 5V3z" />
                    </svg>
                  </button>
                ) : (
                  <div className="w-[220px] overflow-y-auto border-r border-border pr-3 transition-all">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-muted uppercase tracking-wide">
                        Collections
                      </span>
                      <button
                        onClick={() => setSidebarCollapsed(true)}
                        className="bg-transparent border-none text-muted hover:text-foreground cursor-pointer p-0"
                        aria-label="Collapse sidebar"
                      >
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 16 16"
                          fill="currentColor"
                        >
                          <path d="M10 3l-5 5 5 5V3z" />
                        </svg>
                      </button>
                    </div>
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
              </div>
            )}

            {/* Papers list */}
            <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0">
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
                    {s === "all"
                      ? "All"
                      : s === "synced"
                        ? "Synced"
                        : "Not Synced"}
                  </button>
                ))}
              </div>

              {papersLoading && papers.length === 0 ? (
                <PaperListSkeleton />
              ) : papers.length === 0 ? (
                <EmptyState
                  message={
                    debouncedSearch
                      ? "No papers match your search."
                      : "No papers found."
                  }
                  hint="Try a different search or collection"
                />
              ) : (
                <>
                  <div className="flex flex-col gap-2">
                    {papers.map((paper) => (
                      <button
                        key={paper.key}
                        onClick={() => handleSelectPaper(paper)}
                        className="group bg-surface border border-border rounded p-4 text-left cursor-pointer hover:border-accent transition-all hover:shadow-md hover:shadow-black/10 w-full"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex flex-col gap-1 min-w-0">
                            <span
                              className="text-sm font-medium truncate"
                              title={paper.title || "Untitled"}
                            >
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
                                aria-label="View LLM cost"
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

                  <Pagination
                    page={page}
                    totalPages={totalPages}
                    totalItems={totalPapers}
                    pageSize={PAGE_SIZE}
                    onPageChange={setPage}
                  />
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
            aria-label="Back to papers"
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
          <AnnotationListSkeleton />
        ) : annotations.length === 0 ? (
          <EmptyState
            message="No annotations found for this paper."
            hint="Highlight text in Zotero to create annotations"
          />
        ) : (
          <>
            <div className="flex flex-col gap-3 flex-1 overflow-y-auto min-h-0 pb-16">
              {groupedAnnotations.map((group) => (
                <div key={group.color} className="flex flex-col gap-2">
                  {groupedAnnotations.length > 1 && (
                    <div className="flex items-center gap-2 text-xs text-muted pt-1">
                      <span
                        className="px-2 py-0.5 rounded-full text-[10px] font-medium"
                        style={{
                          backgroundColor: `${group.color || "#888"}20`,
                          color: group.color || "#888",
                        }}
                      >
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
              <div className="flex items-center gap-2">
                <select
                  value={model}
                  onChange={(e) =>
                    setModel(e.target.value as "haiku" | "sonnet")
                  }
                  className="bg-surface border border-border rounded px-2 py-2 text-xs text-foreground outline-none focus:border-accent cursor-pointer"
                >
                  <option value="haiku">Haiku 4.5</option>
                  <option value="sonnet">Sonnet 4.6</option>
                </select>
                <button
                  onClick={handleProcess}
                  disabled={checkedCount === 0}
                  className="bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Process {checkedCount} annotation
                  {checkedCount !== 1 ? "s" : ""}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    );
  }

  // --- Processing step ---
  return (
    <div className="flex flex-col gap-4 flex-1 min-h-0">
      <StepIndicator current="processing" onNavigate={handleStepNavigate} />

      <div className="flex items-center gap-3">
        <button
          onClick={handleBackToPapers}
          className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
          aria-label="Back to papers"
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
        <ProcessingSpinner paperTitle={selectedPaper?.title || "Untitled"} />
      )}

      {!processing && resultChangeset && (
        <div className="flex flex-col gap-3 flex-1 min-h-0">
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
        <EmptyState message="No results yet." />
      )}
    </div>
  );
}
