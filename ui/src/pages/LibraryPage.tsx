import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router";
import {
  fetchZoteroStatus,
  fetchZoteroPapers,
  fetchZoteroCollections,
  fetchZoteroPapersCacheStatus,
  triggerZoteroPapersRefresh,
  fetchChangesetCost,
} from "../api/client";
import type {
  ZoteroStatus,
  ZoteroPaperSummary,
  ZoteroCollection,
  TokenUsage,
} from "../types";
import { ErrorAlert } from "../components/ErrorAlert";
import { formatError, formatTokens } from "../utils";
import {
  CollectionTree,
  CollectionTreeSkeleton,
} from "../components/CollectionTree";
import { Skeleton } from "../components/Skeleton";
import { Pagination } from "../components/Pagination";
import { useClickOutside } from "../hooks/useClickOutside";

const PAGE_SIZE = 25;
const POLL_INTERVAL_MS = 3000;
const SEARCH_DEBOUNCE_MS = 300;

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

export function LibraryPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<ZoteroStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [papers, setPapers] = useState<ZoteroPaperSummary[]>([]);
  const [papersLoading, setPapersLoading] = useState(false);
  const [cacheUpdatedAt, setCacheUpdatedAt] = useState<string | null>(null);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [totalPapers, setTotalPapers] = useState(0);

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(0);
  const [syncStatus, setSyncStatus] = useState<"all" | "synced" | "unsynced">(
    "unsynced",
  );

  const [collections, setCollections] = useState<ZoteroCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [selectedCollectionKey, setSelectedCollectionKey] = useState<
    string | null
  >(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [costPopoverKey, setCostPopoverKey] = useState<string | null>(null);

  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  useEffect(() => {
    if (!status?.configured) return;
    loadPapers({
      collectionKey: selectedCollectionKey ?? undefined,
      offset: page * PAGE_SIZE,
      search: debouncedSearch || undefined,
      syncStatus,
    });
  }, [
    status?.configured,
    selectedCollectionKey,
    page,
    debouncedSearch,
    syncStatus,
    loadPapers,
  ]);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  async function handleRefresh() {
    try {
      await triggerZoteroPapersRefresh();
      setSyncInProgress(true);

      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
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

  function handleSelectPaper(paper: ZoteroPaperSummary) {
    navigate(`/library/${paper.key}`, { state: { paper } });
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

  const isInitialSync = !cacheUpdatedAt && papers.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold m-0">Zotero Library</h2>
          {syncInProgress && (
            <span className="text-xs text-muted animate-pulse">Syncing...</span>
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

          <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title or author..."
              className="w-full bg-surface border border-border rounded px-3 py-2 text-sm text-foreground placeholder:text-muted outline-none focus:border-accent"
            />

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
