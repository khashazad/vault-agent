import { useState, useEffect, useMemo } from "react";
import { useParams, useLocation, useNavigate } from "react-router";
import { fetchZoteroPaperAnnotations, syncZoteroPaper } from "../api/client";
import type {
  ZoteroPaperSummary,
  ZoteroAnnotationItem,
  Changeset,
} from "../types";
import { ErrorAlert } from "../components/ErrorAlert";
import { ChangesetReview } from "../components/ChangesetReview";
import { Skeleton } from "../components/Skeleton";
import { formatError } from "../utils";

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

type Step = "annotations" | "processing";

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

export function AnnotationsPage() {
  const { paperKey } = useParams<{ paperKey: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const paper =
    (location.state as { paper?: ZoteroPaperSummary })?.paper ?? null;

  const [annotations, setAnnotations] = useState<ZoteroAnnotationItem[]>([]);
  const [annotationsLoading, setAnnotationsLoading] = useState(true);
  const [checkedKeys, setCheckedKeys] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState<"haiku" | "sonnet">("sonnet");

  const [step, setStep] = useState<Step>("annotations");
  const [processing, setProcessing] = useState(false);
  const [resultChangeset, setResultChangeset] = useState<Changeset | null>(
    null,
  );

  const [paperTitle, setPaperTitle] = useState(paper?.title || "Untitled");

  useEffect(() => {
    if (!paperKey) return;
    setAnnotationsLoading(true);
    fetchZoteroPaperAnnotations(paperKey)
      .then((res) => {
        setAnnotations(res.annotations);
        setCheckedKeys(new Set(res.annotations.map((a) => a.key)));
        if (!paper) setPaperTitle(res.paper_title);
      })
      .catch((err) => setError(formatError(err)))
      .finally(() => setAnnotationsLoading(false));
  }, [paperKey, paper]);

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
    if (!paperKey) return;
    setStep("processing");
    setProcessing(true);
    setError(null);
    setResultChangeset(null);

    const excluded = annotations
      .filter((a) => !checkedKeys.has(a.key))
      .map((a) => a.key);

    try {
      const changeset = await syncZoteroPaper(
        paperKey,
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

  function handleBackToLibrary() {
    navigate("/library");
  }

  function handleBackToAnnotations() {
    setStep("annotations");
    setProcessing(false);
    setResultChangeset(null);
    setError(null);
  }

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

  const checkedCount = checkedKeys.size;

  // Processing results view
  if (step === "processing") {
    return (
      <div className="flex flex-col gap-4 flex-1 min-h-0">
        <div className="flex items-center gap-1 text-xs mb-4">
          <button
            onClick={handleBackToLibrary}
            className="px-2 py-0.5 rounded border-none bg-transparent text-accent cursor-pointer underline"
          >
            Papers
          </button>
          <span className="text-muted mx-1">&rarr;</span>
          <button
            onClick={handleBackToAnnotations}
            className="px-2 py-0.5 rounded border-none bg-transparent text-accent cursor-pointer underline"
          >
            Annotations
          </button>
          <span className="text-muted mx-1">&rarr;</span>
          <span className="px-2 py-0.5 rounded bg-accent text-crust font-medium cursor-default">
            Results
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleBackToLibrary}
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

        {processing && <ProcessingSpinner paperTitle={paperTitle} />}

        {!processing && resultChangeset && (
          <div className="flex flex-col gap-3 flex-1 min-h-0">
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
              onDone={handleBackToLibrary}
            />
          </div>
        )}

        {!processing && !resultChangeset && !error && (
          <EmptyState message="No results yet." />
        )}
      </div>
    );
  }

  // Annotations view
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1 text-xs mb-4">
        <button
          onClick={handleBackToLibrary}
          className="px-2 py-0.5 rounded border-none bg-transparent text-accent cursor-pointer underline"
        >
          Papers
        </button>
        <span className="text-muted mx-1">&rarr;</span>
        <span
          className="px-2 py-0.5 rounded bg-accent text-crust font-medium cursor-default"
          aria-current="step"
        >
          Annotations
        </span>
        <span className="text-muted mx-1">&rarr;</span>
        <span className="px-2 py-0.5 rounded bg-transparent text-muted cursor-default">
          Results
        </span>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleBackToLibrary}
          className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
          aria-label="Back to papers"
          title="Back to papers"
        >
          &larr;
        </button>
        <div className="flex flex-col gap-0.5 min-w-0">
          <h2 className="text-base font-semibold m-0 truncate">{paperTitle}</h2>
          {paper && (
            <span className="text-xs text-muted">
              {paper.authors.join(", ")}
              {paper.year ? ` (${paper.year})` : ""}
            </span>
          )}
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
                onChange={(e) => setModel(e.target.value as "haiku" | "sonnet")}
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
