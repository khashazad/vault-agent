import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import {
  fetchZoteroStatus,
  fetchZoteroPapers,
  fetchZoteroPapersCacheStatus,
  triggerZoteroPapersRefresh,
  fetchChangesetCost,
} from "../api/client";
import type { ZoteroStatus, ZoteroPaperSummary, TokenUsage } from "../types";
import { ErrorAlert } from "../components/ErrorAlert";
import { formatError, formatTokens } from "../utils";
import { Skeleton } from "../components/Skeleton";
import { Pagination } from "../components/Pagination";
import { useClickOutside } from "../hooks/useClickOutside";

const PAGE_SIZE = 25;
const POLL_INTERVAL_MS = 3000;
const SEARCH_DEBOUNCE_MS = 300;

function PaperListSkeleton() {
  return (
    <div className="flex flex-col">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className="py-4 px-6 flex flex-col gap-2 border-b border-border/5"
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
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <svg
        width="32"
        height="32"
        viewBox="0 0 16 16"
        fill="currentColor"
        className="text-muted/30"
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
  const [searchParams] = useSearchParams();
  const selectedCollectionKey = searchParams.get("collection");

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

  useEffect(() => {
    fetchZoteroStatus()
      .then((s) => setStatus(s))
      .catch((err) => setError(formatError(err)))
      .finally(() => setLoading(false));
  }, []);

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

  // Reset page when collection changes
  useEffect(() => {
    setPage(0);
    setSearchQuery("");
    setDebouncedSearch("");
  }, [selectedCollectionKey]);

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

  const totalPages = Math.ceil(totalPapers / PAGE_SIZE);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-muted text-sm">Loading Zotero status...</span>
      </div>
    );
  }

  if (status && !status.configured) {
    return (
      <div className="py-6 px-8">
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
      </div>
    );
  }

  const isInitialSync = !cacheUpdatedAt && papers.length === 0;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Header bar */}
      <div className="bg-surface-dim px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold m-0 font-display">
            Zotero Library
          </h2>
          {syncInProgress && (
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-[pulse-dot_1s_infinite]" />
              <span className="text-xs text-muted">Syncing...</span>
            </div>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={syncInProgress}
          className="text-xs bg-transparent border border-purple/50 text-purple rounded-lg px-4 py-1.5 cursor-pointer disabled:opacity-50 hover:bg-purple/10 transition-colors"
        >
          {syncInProgress ? "Syncing..." : "Sync with Zotero"}
        </button>
      </div>

      {error && (
        <div className="px-6 pt-3">
          <ErrorAlert message={error} />
        </div>
      )}

      {/* Content */}
      {isInitialSync ? (
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="bg-surface rounded-xl p-8 flex flex-col items-center gap-3">
            <span className="inline-block w-2 h-2 rounded-full bg-accent animate-[pulse-dot_1s_infinite]" />
            <span className="text-sm text-muted">Syncing with Zotero...</span>
            <span className="text-xs text-muted/70">
              Papers will appear here once the initial sync completes.
            </span>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-4 min-h-0">
          {/* Search */}
          <div className="relative">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by title or author..."
              className="w-full bg-surface border border-border rounded-xl pl-10 pr-4 py-2.5 text-sm text-text placeholder:text-muted/60 outline-none focus:border-teal transition-colors"
            />
          </div>

          {/* Filter pills */}
          <div className="flex gap-2">
            {(["all", "synced", "unsynced"] as const).map((s) => (
              <button
                key={s}
                onClick={() => handleSyncStatusChange(s)}
                className={`px-3.5 py-1.5 text-xs font-medium rounded-full transition-colors ${
                  syncStatus === s
                    ? "bg-purple text-crust"
                    : "bg-surface text-muted hover:text-text border border-border/50"
                }`}
              >
                {s === "all" ? "All" : s === "synced" ? "Synced" : "Not Synced"}
              </button>
            ))}
          </div>

          {/* Paper list */}
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
              <div className="flex flex-col">
                {papers.map((paper) => (
                  <button
                    key={paper.key}
                    onClick={() => handleSelectPaper(paper)}
                    className="group flex items-center justify-between gap-3 py-3.5 px-4 text-left cursor-pointer border-none bg-transparent border-b border-b-border/5 hover:bg-surface-high transition-colors w-full rounded-lg"
                  >
                    <div className="flex flex-col gap-1 min-w-0">
                      <span
                        className="text-sm font-semibold text-teal truncate"
                        title={paper.title || "Untitled"}
                      >
                        {paper.title || "Untitled"}
                      </span>
                      <span
                        className="text-xs text-muted/70 italic truncate"
                        title={
                          paper.authors.length > 0
                            ? paper.authors.join(", ")
                            : "Unknown author"
                        }
                      >
                        {paper.authors.length > 0
                          ? paper.authors.length > 2
                            ? `${paper.authors.slice(0, 2).join(", ")} et al.`
                            : paper.authors.join(", ")
                          : "Unknown author"}
                        {paper.year ? ` (${paper.year})` : ""}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0 relative">
                      {paper.annotation_count != null &&
                        paper.annotation_count > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-elevated font-mono uppercase tracking-wide">
                            {paper.annotation_count}{" "}
                            {paper.annotation_count === 1
                              ? "annotation"
                              : "annotations"}
                          </span>
                        )}
                      {paper.changeset_id && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setCostPopoverKey(
                              costPopoverKey === paper.key ? null : paper.key,
                            );
                          }}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-surface border border-border text-muted hover:text-accent hover:border-accent cursor-pointer"
                          aria-label="View LLM cost"
                          title="View LLM cost"
                        >
                          $
                        </button>
                      )}
                      {costPopoverKey === paper.key && paper.changeset_id && (
                        <CostPopover
                          changesetId={paper.changeset_id}
                          onClose={() => setCostPopoverKey(null)}
                        />
                      )}
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap ${
                          paper.last_synced
                            ? "bg-green/15 text-green"
                            : "bg-red/15 text-red"
                        }`}
                      >
                        {paper.last_synced
                          ? `Synced ${new Date(paper.last_synced).toLocaleDateString()}`
                          : "Never synced"}
                      </span>
                      {/* Hover chevron */}
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="text-muted/0 group-hover:text-muted transition-colors"
                      >
                        <path d="m9 18 6-6-6-6" />
                      </svg>
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
      )}

      {/* Status bar */}
      <div className="bg-surface px-6 py-2.5 flex items-center justify-between text-xs text-muted shrink-0 border-t border-border/20">
        <div className="flex items-center gap-2">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green" />
          <span>Vault Online</span>
        </div>
        <div className="flex items-center gap-4">
          <span>
            {totalPapers} {totalPapers === 1 ? "paper" : "papers"}
          </span>
          {cacheUpdatedAt && (
            <span>
              Last sync{" "}
              {new Date(cacheUpdatedAt).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
