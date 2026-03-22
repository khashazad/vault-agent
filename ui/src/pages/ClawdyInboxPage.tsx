import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import type { ChangesetSummary, ClawdyConfig, ClawdyStatus } from "../types";
import {
  fetchClawdyConfig,
  updateClawdyConfig,
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

const INTERVAL_OPTIONS = [
  { value: 60, label: "1 min" },
  { value: 300, label: "5 min" },
  { value: 900, label: "15 min" },
  { value: 1800, label: "30 min" },
];

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

function ConfigSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <Skeleton h="h-4" w="w-48" />
        <Skeleton h="h-5" w="w-10" className="rounded-full" />
      </div>
      <div className="flex items-center gap-3">
        <Skeleton h="h-4" w="w-32" />
        <Skeleton h="h-8" w="w-24" />
        <Skeleton h="h-8" w="w-24" />
      </div>
    </div>
  );
}

export function ClawdyInboxPage() {
  const navigate = useNavigate();

  const [config, setConfig] = useState<ClawdyConfig | null>(null);
  const [status, setStatus] = useState<ClawdyStatus | null>(null);
  const [summaries, setSummaries] = useState<ChangesetSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);

  const [configLoading, setConfigLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = useCallback(async () => {
    try {
      const [cfg, st] = await Promise.all([
        fetchClawdyConfig(),
        fetchClawdyStatus(),
      ]);
      setConfig(cfg);
      setStatus(st);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setConfigLoading(false);
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
    loadConfig();
  }, [loadConfig]);

  useEffect(() => {
    loadChangesets();
  }, [loadChangesets]);

  async function handleToggleEnabled() {
    if (!config) return;
    setError(null);
    try {
      const updated = await updateClawdyConfig({ enabled: !config.enabled });
      setConfig(updated);
    } catch (err) {
      setError(formatError(err));
    }
  }

  async function handleIntervalChange(value: number) {
    setError(null);
    try {
      const updated = await updateClawdyConfig({ interval: value });
      setConfig(updated);
    } catch (err) {
      setError(formatError(err));
    }
  }

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

      {/* Config / status bar */}
      {configLoading ? (
        <ConfigSkeleton />
      ) : config && status ? (
        <div className="bg-surface border border-border rounded-lg p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-4 flex-wrap">
              {/* Copy vault path */}
              {status.copy_vault_path && (
                <span className="text-xs text-muted font-mono truncate max-w-xs">
                  {status.copy_vault_path}
                </span>
              )}

              {/* Enable/disable toggle */}
              <button
                onClick={handleToggleEnabled}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer border-none ${
                  config.enabled ? "bg-green" : "bg-elevated"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 rounded-full bg-text transition-transform ${
                    config.enabled ? "translate-x-4.5" : "translate-x-0.5"
                  }`}
                />
              </button>
              <span className="text-xs text-muted">
                {config.enabled ? "Enabled" : "Disabled"}
              </span>

              {/* Interval selector */}
              <select
                value={config.interval}
                onChange={(e) => handleIntervalChange(Number(e.target.value))}
                className="text-xs bg-elevated border border-border rounded px-2 py-1 text-text cursor-pointer"
              >
                {INTERVAL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-3">
              {/* Pending count */}
              {status.pending_changeset_count > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow/15 text-yellow">
                  {status.pending_changeset_count} pending
                </span>
              )}

              {/* Check Now */}
              <button
                onClick={handleCheckNow}
                disabled={syncing}
                className="text-xs px-3 py-1.5 rounded bg-accent/15 text-accent border-none cursor-pointer hover:bg-accent/25 disabled:opacity-50"
              >
                {syncing ? "Checking..." : "Check Now"}
              </button>
            </div>
          </div>

          {/* Status row */}
          <div className="flex items-center gap-4 text-[11px] text-muted flex-wrap">
            {status.last_poll && (
              <span>
                Last poll: {new Date(status.last_poll).toLocaleString()}
              </span>
            )}
            {status.last_error && (
              <span className="text-red truncate max-w-md">
                Error: {status.last_error}
              </span>
            )}
          </div>
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
                      <span className="text-xs font-mono text-muted truncate">
                        {cs.id.slice(0, 8)}...
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
                    <span className="text-xs text-muted">
                      {new Date(cs.created_at).toLocaleDateString()}
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
