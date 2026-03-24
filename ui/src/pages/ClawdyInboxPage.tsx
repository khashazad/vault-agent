import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import type { ChangesetSummary, ClawdyStatus } from "../types";
import {
  fetchClawdyStatus,
  triggerClawdySync,
  fetchChangesets,
} from "../api/client";
import { formatError } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { StatusBadge } from "../components/StatusBadge";
import { Pagination } from "../components/Pagination";
import { Skeleton } from "../components/Skeleton";

const PAGE_SIZE = 25;

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

export function ClawdyInboxPage() {
  const navigate = useNavigate();

  const [status, setStatus] = useState<ClawdyStatus | null>(null);
  const [summaries, setSummaries] = useState<ChangesetSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);

  const [statusLoading, setStatusLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const st = await fetchClawdyStatus();
      setStatus(st);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setStatusLoading(false);
    }
  }, []);

  const loadChangesets = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await fetchChangesets({
        source_type: "clawdy",
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
  }, [page]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    loadChangesets();
  }, [loadChangesets]);

  async function handleCheckNow() {
    setSyncing(true);
    setError(null);
    try {
      await triggerClawdySync();
      const st = await fetchClawdyStatus();
      setStatus(st);
      await loadChangesets();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSyncing(false);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4 py-6 px-8">
      <h2 className="text-base font-semibold m-0">Clawdy Inbox</h2>

      {error && <ErrorAlert message={error} />}

      {/* Status line */}
      {statusLoading ? (
        <div className="flex items-center gap-4">
          <Skeleton h="h-3" w="w-16" />
          <Skeleton h="h-3" w="w-32" />
          <Skeleton h="h-6" w="w-20" />
        </div>
      ) : status ? (
        <div className="flex items-center gap-4 flex-wrap text-xs text-muted">
          {status.last_auto_sync != null && status.last_auto_sync > 0 && (
            <span>Auto-synced {status.last_auto_sync} files</span>
          )}
          {status.last_poll && (
            <span>
              Last poll: {new Date(status.last_poll).toLocaleString()}
            </span>
          )}
          {status.pending_changeset_count > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow/15 text-yellow">
              {status.pending_changeset_count} pending
            </span>
          )}
          {status.last_error && (
            <span className="text-red truncate max-w-md">
              Error: {status.last_error}
            </span>
          )}
          <button
            onClick={handleCheckNow}
            disabled={syncing}
            className="text-xs px-3 py-1.5 rounded bg-accent/15 text-accent border-none cursor-pointer hover:bg-accent/25 disabled:opacity-50"
          >
            {syncing ? "Checking..." : "Check Now"}
          </button>
        </div>
      ) : null}

      {/* Changeset list */}
      {listLoading && summaries.length === 0 ? (
        <ListSkeleton />
      ) : summaries.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <span className="text-sm text-muted">No clawdy changesets yet.</span>
          <span className="text-xs text-muted/70">
            Changes from OpenClaw will appear here after polling
          </span>
        </div>
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
