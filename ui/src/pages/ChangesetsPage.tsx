import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router";
import type { ChangesetSummary } from "../types";
import { fetchChangesets, deleteChangeset } from "../api/client";
import { formatError } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { StatusBadge } from "../components/StatusBadge";
import { Pagination } from "../components/Pagination";
import { Skeleton } from "../components/Skeleton";
import { useClickOutside } from "../hooks/useClickOutside";

type StatusFilter =
  | "all"
  | "pending"
  | "applied"
  | "rejected"
  | "revision_requested";

const PAGE_SIZE = 25;

function TrashIcon() {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M5.5 5.5a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5.5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0zm3 .5a.5.5 0 0 1-.5-.5.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6a.5.5 0 0 1 .5-.5" />
      <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1 0-2H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1M4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM6 2h4a.5.5 0 0 0-.5-.5h-3A.5.5 0 0 0 6 2" />
    </svg>
  );
}

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

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded p-4 flex flex-col gap-2"
        >
          <div className="flex items-center gap-2">
            <Skeleton h="h-3" w="w-20" />
            <Skeleton h="h-4" w="w-16" className="rounded-full" />
          </div>
          <Skeleton h="h-3" w="w-2/5" />
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
        <path d="M4 .5a.5.5 0 0 0-1 0V1H2a2 2 0 0 0-2 2v1h16V3a2 2 0 0 0-2-2h-1V.5a.5.5 0 0 0-1 0V1H4zM16 14V5H0v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2" />
      </svg>
      <span className="text-sm text-muted">{message}</span>
      {hint && <span className="text-xs text-muted/70">{hint}</span>}
    </div>
  );
}

export function ChangesetsPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<ChangesetSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [listLoading, setListLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

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
    loadList();
  }, [loadList]);

  const openDeleteConfirm = useCallback((id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(id);
  }, []);

  const cancelDelete = useCallback(() => {
    setConfirmDeleteId(null);
  }, []);

  const confirmDelete = useCallback(
    async (id: string) => {
      setConfirmDeleteId(null);
      setDeleting(id);
      setError(null);
      try {
        await deleteChangeset(id);
        loadList();
      } catch (err) {
        setError(formatError(err));
      } finally {
        setDeleting(null);
      }
    },
    [loadList],
  );

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4 py-6 px-8">
      <h2 className="text-base font-semibold m-0">Changeset History</h2>

      {error && <ErrorAlert message={error} />}

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
        <ListSkeleton />
      ) : summaries.length === 0 ? (
        <EmptyState
          message="No changesets found."
          hint="Process some papers to see changesets here"
        />
      ) : (
        <>
          <div className="flex flex-col gap-2">
            {summaries.map((cs) => (
              <div
                key={cs.id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/changesets/${cs.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ")
                    navigate(`/changesets/${cs.id}`);
                }}
                className="bg-surface border border-border rounded p-4 text-left cursor-pointer hover:border-accent transition-colors w-full focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-col gap-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted">
                        {new Date(cs.created_at).toLocaleDateString(undefined, {
                          month: "short",
                          day: "numeric",
                          hour: "numeric",
                          minute: "2-digit",
                        })}
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
                    <div className="relative">
                      <button
                        onClick={(e) => openDeleteConfirm(cs.id, e)}
                        disabled={deleting === cs.id}
                        className="text-muted hover:text-red bg-transparent border-none cursor-pointer text-sm p-0 leading-none disabled:opacity-50"
                        aria-label="Delete changeset"
                        title="Delete changeset"
                        data-testid={`delete-${cs.id}`}
                      >
                        <TrashIcon />
                      </button>
                      {confirmDeleteId === cs.id && (
                        <DeleteConfirmPopover
                          onConfirm={() => confirmDelete(cs.id)}
                          onCancel={cancelDelete}
                        />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            totalItems={total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
