import { useState, useEffect, useCallback } from "react";
import type { MigrationNote, MigrationNoteStatus } from "../types";
import {
  fetchMigrationNotes,
  updateMigrationNote,
  applyMigration,
} from "../api/client";
import { formatError } from "../utils";
import { MarkdownPreview } from "./MarkdownPreview";
import { DiffViewer } from "./DiffViewer";

interface Props {
  jobId: string;
  onApply: () => void;
}

type FilterTab = "all" | "proposed" | "approved" | "rejected";

const TABS: { label: string; value: FilterTab }[] = [
  { label: "All", value: "all" },
  { label: "Proposed", value: "proposed" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
];

const PAGE_SIZE = 25;

const STATUS_COLORS: Record<string, string> = {
  proposed: "bg-yellow-bg text-yellow",
  approved: "bg-green-bg text-green",
  rejected: "bg-red-bg text-red",
  applied: "bg-blue-bg text-blue",
  pending: "bg-elevated text-muted",
  processing: "bg-elevated text-muted",
  failed: "bg-red-bg text-red",
  skipped: "bg-elevated text-muted",
};

export function MigrationNoteReview({ jobId, onApply }: Props) {
  const [notes, setNotes] = useState<MigrationNote[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [updatingIds, setUpdatingIds] = useState<Set<string>>(new Set());

  const loadNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = filter === "all" ? undefined : filter;
      const res = await fetchMigrationNotes(jobId, {
        status,
        offset,
        limit: PAGE_SIZE,
      });
      setNotes(res.notes);
      setTotal(res.total);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }, [jobId, filter, offset]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  useEffect(() => {
    setOffset(0);
    setSelectedId(null);
  }, [filter]);

  const updateNote = useCallback(
    async (noteId: string, status: MigrationNoteStatus) => {
      setUpdatingIds((prev) => new Set(prev).add(noteId));
      try {
        const updated = await updateMigrationNote(jobId, noteId, { status });
        setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)));
      } catch (err) {
        setError(formatError(err));
      } finally {
        setUpdatingIds((prev) => {
          const next = new Set(prev);
          next.delete(noteId);
          return next;
        });
      }
    },
    [jobId],
  );

  const bulkUpdate = useCallback(
    async (status: MigrationNoteStatus) => {
      const proposed = notes.filter((n) => n.status === "proposed");
      await Promise.all(proposed.map((n) => updateNote(n.id, status)));
    },
    [notes, updateNote],
  );

  const handleApply = useCallback(async () => {
    setApplying(true);
    try {
      await applyMigration(jobId);
      onApply();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setApplying(false);
    }
  }, [jobId, onApply]);

  const selected = notes.find((n) => n.id === selectedId) ?? null;
  const proposedCount = notes.filter((n) => n.status === "proposed").length;
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Review Migration Notes</h3>
        <div className="flex gap-2">
          {proposedCount > 0 && (
            <>
              <button
                onClick={() => bulkUpdate("approved")}
                className="bg-elevated text-text border border-border py-1 px-3 rounded text-xs"
              >
                Approve All Visible
              </button>
              <button
                onClick={() => bulkUpdate("rejected")}
                className="bg-transparent text-text border border-border py-1 px-3 rounded text-xs"
              >
                Reject All Visible
              </button>
            </>
          )}
          <button
            onClick={handleApply}
            disabled={applying}
            className="bg-green text-crust border-none py-1 px-4 rounded text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {applying ? "Applying..." : "Apply to Vault"}
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex border border-border rounded overflow-hidden w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setFilter(tab.value)}
            className={`text-xs py-1 px-3 border-none ${
              filter === tab.value
                ? "bg-accent text-crust"
                : "bg-elevated text-muted"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && <p className="text-red text-xs">{error}</p>}

      {loading ? (
        <div className="text-muted text-sm p-4">Loading...</div>
      ) : notes.length === 0 ? (
        <div className="text-muted text-sm p-4">No notes found.</div>
      ) : (
        <div className="flex flex-1 min-h-0 gap-3">
          {/* Note list */}
          <div className="w-72 shrink-0 flex flex-col border border-border rounded overflow-hidden">
            <div className="flex-1 overflow-y-auto">
              {notes.map((note) => (
                <button
                  key={note.id}
                  onClick={() => {
                    setSelectedId(note.id);
                    setShowDiff(false);
                  }}
                  className={`w-full text-left p-2 border-b border-border text-xs flex flex-col gap-1 ${
                    selectedId === note.id
                      ? "bg-accent/15 border-l-2 border-l-accent"
                      : "bg-surface"
                  }`}
                >
                  <span className="text-text font-mono truncate">
                    {note.source_path}
                  </span>
                  <span
                    className={`inline-block w-fit px-1.5 py-0.5 rounded text-[10px] uppercase ${STATUS_COLORS[note.status] ?? "bg-elevated text-muted"}`}
                  >
                    {note.status}
                  </span>
                </button>
              ))}
            </div>
            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between p-2 border-t border-border text-xs text-muted">
                <button
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                  className="bg-transparent text-muted border-none disabled:opacity-30"
                >
                  Prev
                </button>
                <span>
                  {currentPage}/{totalPages}
                </span>
                <button
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= total}
                  className="bg-transparent text-muted border-none disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            )}
          </div>

          {/* Detail panel */}
          <div className="flex-1 min-w-0 flex flex-col border border-border rounded p-3 overflow-y-auto">
            {!selected ? (
              <div className="text-muted text-sm m-auto">
                Select a note to review
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-mono text-muted flex-1 truncate">
                    {selected.source_path}
                  </span>
                  {selected.proposed_content != null && (
                    <div className="flex border border-border rounded overflow-hidden">
                      <button
                        onClick={() => setShowDiff(false)}
                        className={`text-[11px] py-0.5 px-2.5 border-none ${
                          !showDiff
                            ? "bg-accent text-crust"
                            : "bg-elevated text-muted"
                        }`}
                      >
                        Side-by-side
                      </button>
                      <button
                        onClick={() => setShowDiff(true)}
                        className={`text-[11px] py-0.5 px-2.5 border-none ${
                          showDiff
                            ? "bg-accent text-crust"
                            : "bg-elevated text-muted"
                        }`}
                      >
                        Diff
                      </button>
                    </div>
                  )}
                  {(selected.status === "proposed" ||
                    selected.status === "approved" ||
                    selected.status === "rejected") && (
                    <div className="flex gap-1">
                      <button
                        onClick={() => updateNote(selected.id, "approved")}
                        disabled={
                          selected.status === "approved" ||
                          updatingIds.has(selected.id)
                        }
                        className="bg-green text-crust border-none py-1 px-3 rounded text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => updateNote(selected.id, "rejected")}
                        disabled={
                          selected.status === "rejected" ||
                          updatingIds.has(selected.id)
                        }
                        className="bg-transparent text-red border border-red py-1 px-3 rounded text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>

                {showDiff && selected.proposed_content != null ? (
                  <DiffViewer
                    diff={selected.diff ?? ""}
                    filePath={selected.source_path}
                    isNew={false}
                    originalContent={selected.original_content}
                    proposedContent={selected.proposed_content}
                  />
                ) : selected.proposed_content != null ? (
                  <div className="grid grid-cols-2 gap-3 flex-1 min-h-0">
                    <div className="flex flex-col min-h-0">
                      <span className="text-[10px] text-muted uppercase mb-1">
                        Original
                      </span>
                      <div className="flex-1 overflow-y-auto border border-border rounded p-2">
                        <MarkdownPreview content={selected.original_content} />
                      </div>
                    </div>
                    <div className="flex flex-col min-h-0">
                      <span className="text-[10px] text-muted uppercase mb-1">
                        Proposed
                      </span>
                      <div className="flex-1 overflow-y-auto border border-border rounded p-2">
                        <MarkdownPreview content={selected.proposed_content} />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 overflow-y-auto border border-border rounded p-2">
                    <MarkdownPreview content={selected.original_content} />
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
