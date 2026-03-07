import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchZoteroStatus,
  fetchZoteroPapers,
  fetchZoteroPaperAnnotations,
  fetchZoteroCollections,
  fetchZoteroPapersCacheStatus,
  triggerZoteroPapersRefresh,
  syncZoteroPaper,
} from "../api/client";
import type {
  ZoteroStatus,
  ZoteroPaperSummary,
  ZoteroAnnotationItem,
  ZoteroCollection,
  Changeset,
} from "../types";
import { ErrorAlert } from "./ErrorAlert";
import { formatError } from "../utils";
import { CollectionTree } from "./CollectionTree";

type Step = "papers" | "annotations" | "processing";

const CACHE_POLL_INTERVAL = 30_000; // 30 seconds

interface Props {
  onViewChange: (view: string) => void;
}

export function ZoteroSync({ onViewChange }: Props) {
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

  // Collections
  const [collections, setCollections] = useState<ZoteroCollection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);
  const [selectedCollectionKey, setSelectedCollectionKey] = useState<string | null>(null);

  // Annotations step
  const [selectedPaper, setSelectedPaper] = useState<ZoteroPaperSummary | null>(null);
  const [annotations, setAnnotations] = useState<ZoteroAnnotationItem[]>([]);
  const [annotationsLoading, setAnnotationsLoading] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState<Set<string>>(new Set());

  // Processing step
  const [processing, setProcessing] = useState(false);
  const [resultChangeset, setResultChangeset] = useState<Changeset | null>(null);

  // Track last known cache timestamp for polling comparison
  const lastCacheUpdatedAtRef = useRef<string | null>(null);

  const loadPapers = useCallback(async (collectionKey?: string | null) => {
    setPapersLoading(true);
    setError(null);
    try {
      const res = await fetchZoteroPapers(collectionKey ?? undefined);
      setPapers(res.papers);
      setCacheUpdatedAt(res.cache_updated_at);
      lastCacheUpdatedAtRef.current = res.cache_updated_at;
    } catch (err) {
      setError(formatError(err));
    } finally {
      setPapersLoading(false);
    }
  }, []);

  const loadCollections = useCallback(async () => {
    setCollectionsLoading(true);
    try {
      const res = await fetchZoteroCollections();
      setCollections(res.collections);
    } catch (err) {
      // Non-fatal — collections sidebar just won't show
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
          loadPapers();
          loadCollections();
        }
      })
      .catch((err) => setError(formatError(err)))
      .finally(() => setLoading(false));
  }, [loadPapers, loadCollections]);

  // Poll cache status every 30s; refetch papers when cache_updated_at changes
  useEffect(() => {
    if (!status?.configured) return;

    const interval = setInterval(async () => {
      try {
        const cacheStatus = await fetchZoteroPapersCacheStatus();
        setSyncInProgress(cacheStatus.sync_in_progress);

        if (
          cacheStatus.cache_updated_at &&
          cacheStatus.cache_updated_at !== lastCacheUpdatedAtRef.current
        ) {
          // Cache was updated — refetch papers
          const res = await fetchZoteroPapers();
          setPapers(res.papers);
          setCacheUpdatedAt(res.cache_updated_at);
          lastCacheUpdatedAtRef.current = res.cache_updated_at;
        }
      } catch {
        // Polling failure is non-fatal
      }
    }, CACHE_POLL_INTERVAL);

    return () => clearInterval(interval);
  }, [status?.configured]);

  async function handleRefresh() {
    try {
      await triggerZoteroPapersRefresh();
      setSyncInProgress(true);
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

  function handleSelectCollection(key: string | null) {
    setSelectedCollectionKey(key);
    loadPapers(key);
  }

  function handleBackToPapers() {
    setStep("papers");
    setSelectedPaper(null);
    setAnnotations([]);
    setCheckedKeys(new Set());
    setResultChangeset(null);
    setError(null);
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
        excluded.length > 0 ? excluded : undefined
      );
      setResultChangeset(changeset);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setProcessing(false);
    }
  }

  async function handleBackToPapersFromResult() {
    handleBackToPapers();
    await loadPapers();
  }

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
    // Empty cache + first sync in progress
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
            {syncInProgress ? "Syncing..." : "Refresh"}
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
            {!collectionsLoading && collections.length > 0 && (
              <div className="w-[220px] flex-shrink-0 overflow-y-auto border-r border-border pr-3">
                <CollectionTree
                  collections={collections}
                  selectedKey={selectedCollectionKey}
                  onSelect={handleSelectCollection}
                />
              </div>
            )}

            {/* Papers list */}
            <div className="flex-1 overflow-y-auto">
              {papersLoading && papers.length === 0 ? (
                <div className="text-muted text-sm">Loading papers...</div>
              ) : papers.length === 0 ? (
                <div className="text-muted text-sm">No papers found.</div>
              ) : (
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
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 ${
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
                    </button>
                  ))}
                </div>
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
          <div className="text-muted text-sm">No annotations found for this paper.</div>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <button
                onClick={toggleAll}
                className="text-xs text-accent bg-transparent border-none cursor-pointer p-0 underline"
              >
                {checkedKeys.size === annotations.length
                  ? "Deselect All"
                  : "Select All"}
              </button>
              <span className="text-xs text-muted">
                {checkedCount} of {annotations.length} selected
              </span>
            </div>

            <div className="flex flex-col gap-2 max-h-[calc(100vh-300px)] overflow-y-auto">
              {annotations.map((ann) => (
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
                        style={{ borderLeft: `3px solid ${ann.color || "#888"}` }}
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

            <button
              onClick={handleProcess}
              disabled={checkedCount === 0}
              className="bg-accent text-white border-none py-2.5 px-5 rounded text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Process {checkedCount} annotation{checkedCount !== 1 ? "s" : ""}
            </button>
          </>
        )}
      </div>
    );
  }

  // --- Processing step ---
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <button
          onClick={handleBackToPapersFromResult}
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
            Running agent on annotations from "{selectedPaper?.title}"...
          </div>
          <div className="text-xs text-muted">
            This may take a moment.
          </div>
        </div>
      )}

      {!processing && resultChangeset && (
        <div className="bg-surface border border-border rounded p-5 flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold m-0">Changeset Created</h3>
            <span className="text-xs font-mono text-muted">
              {resultChangeset.id}
            </span>
          </div>

          <div className="flex gap-4 text-sm">
            <span>
              <span className="text-muted">Proposed changes:</span>{" "}
              <span className="font-medium">
                {resultChangeset.changes.length}
              </span>
            </span>
            <span>
              <span className="text-muted">Status:</span>{" "}
              <span className="font-medium">{resultChangeset.status}</span>
            </span>
          </div>

          {resultChangeset.routing && (
            <div className="text-xs text-muted">
              Route: {resultChangeset.routing.action}{" "}
              {resultChangeset.routing.target_path && (
                <span className="font-mono">
                  → {resultChangeset.routing.target_path}
                </span>
              )}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => onViewChange("preview")}
              className="bg-accent text-white border-none py-2 px-4 rounded text-sm font-medium cursor-pointer"
            >
              View in Preview
            </button>
            <button
              onClick={handleBackToPapersFromResult}
              className="text-sm text-muted bg-transparent border border-border rounded px-4 py-2 cursor-pointer hover:border-accent"
            >
              Back to Papers
            </button>
          </div>
        </div>
      )}

      {!processing && !resultChangeset && !error && (
        <div className="text-muted text-sm">No results yet.</div>
      )}
    </div>
  );
}
