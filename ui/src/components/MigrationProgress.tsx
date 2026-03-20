import { useState, useEffect, useRef } from "react";
import {
  fetchMigrationJob,
  cancelMigration,
  resumeMigration,
} from "../api/client";
import type { MigrationJob, MigrationJobStatus } from "../types";

interface Props {
  jobId: string;
  model?: "haiku" | "sonnet";
  onReviewReady: () => void;
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-accent/15 text-accent",
  migrating: "bg-blue-500/15 text-blue-400",
  review: "bg-green-bg text-green",
  applying: "bg-accent/15 text-accent",
  completed: "bg-green-bg text-green",
  failed: "bg-red-bg text-red",
  cancelled: "bg-surface text-muted border border-border",
};

function StatusBadge({ status }: { status: MigrationJobStatus }) {
  return (
    <span
      className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${STATUS_STYLES[status] ?? "bg-surface text-muted"}`}
    >
      {status}
    </span>
  );
}

const TERMINAL_STATUSES = ["completed", "cancelled"];

export function MigrationProgress({ jobId, model, onReviewReady }: Props) {
  const [job, setJob] = useState<MigrationJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [resuming, setResuming] = useState(false);
  const reviewFiredRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    reviewFiredRef.current = false;

    async function poll() {
      try {
        const data = await fetchMigrationJob(jobId);
        setJob(data);
        setError(null);

        if (data.status === "review" && !reviewFiredRef.current) {
          reviewFiredRef.current = true;
          onReviewReady();
        }

        // Stop polling on terminal or paused states
        if (
          TERMINAL_STATUSES.includes(data.status) ||
          data.status === "failed"
        ) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, onReviewReady]);

  async function handleCancel() {
    setCancelling(true);
    try {
      await cancelMigration(jobId);
      const data = await fetchMigrationJob(jobId);
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCancelling(false);
    }
  }

  async function handleResume() {
    setResuming(true);
    try {
      await resumeMigration(jobId, model);
      // Restart polling
      reviewFiredRef.current = false;
      const poll = async () => {
        try {
          const data = await fetchMigrationJob(jobId);
          setJob(data);
          setError(null);
          if (data.status === "review" && !reviewFiredRef.current) {
            reviewFiredRef.current = true;
            onReviewReady();
          }
          if (
            TERMINAL_STATUSES.includes(data.status) ||
            data.status === "failed"
          ) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
      };
      poll();
      intervalRef.current = setInterval(poll, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setResuming(false);
    }
  }

  const isActive =
    job && (job.status === "pending" || job.status === "migrating");
  const pct =
    job && job.total_notes > 0
      ? Math.round((job.processed_notes / job.total_notes) * 100)
      : 0;

  return (
    <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Migration Progress</h3>
        {job && <StatusBadge status={job.status} />}
      </div>

      {error && (
        <p className="text-[13px] text-red">Error polling job: {error}</p>
      )}

      {job && (
        <>
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[13px] text-muted">
              <span>
                {job.processed_notes} / {job.total_notes} notes
              </span>
              <span>{pct}%</span>
            </div>
            <div className="h-2 bg-base rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {job.batch_mode && (
            <p className="text-[13px] text-blue-400">
              Batch processing — typically completes within 1 hour
            </p>
          )}

          {job.estimated_cost_usd != null && (
            <p className="text-[13px] text-muted">
              Estimated cost:{" "}
              <span className="text-text">
                ${job.estimated_cost_usd.toFixed(2)}
              </span>
              {job.batch_mode && (
                <span className="text-green ml-1">(50% batch discount)</span>
              )}
            </p>
          )}

          {isActive && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="text-[13px] px-3 py-1 rounded border border-red text-red hover:bg-red-bg disabled:opacity-50 transition-colors"
            >
              {cancelling ? "Cancelling..." : "Cancel"}
            </button>
          )}

          {job.status === "failed" && (
            <div className="space-y-2">
              <p className="text-[13px] text-red">
                Migration failed. {job.processed_notes} of {job.total_notes}{" "}
                notes were processed before the failure.
              </p>
              <button
                onClick={handleResume}
                disabled={resuming}
                className="text-[13px] px-3 py-1 rounded bg-accent text-crust disabled:opacity-50 transition-colors"
              >
                {resuming ? "Resuming..." : "Resume Migration"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
