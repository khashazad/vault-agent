import { useState, useEffect, useCallback } from "react";
import type {
  TaxonomyProposal,
  CostEstimate,
  MigrationJob,
  MigrationJobStatus,
} from "../types";
import {
  importTaxonomy,
  updateTaxonomy,
  activateTaxonomy,
  estimateMigrationCost,
  createMigrationJob,
  fetchMigrationJobs,
  fetchTaxonomy,
} from "../api/client";
import { TaxonomyEditor } from "./TaxonomyEditor";
import { MigrationProgress } from "./MigrationProgress";
import { MigrationNoteReview } from "./MigrationNoteReview";
import { ErrorAlert } from "./ErrorAlert";
import { StatusBadge } from "./StatusBadge";
import { Skeleton } from "./Skeleton";

type Step = "list" | "setup" | "taxonomy" | "progress" | "review";

const STORAGE_KEY = "vault-agent:migration-job-id";

// Derive the dashboard step from a migration job's status.
function stepFromStatus(status: MigrationJob["status"]): Step {
  switch (status) {
    case "pending":
    case "migrating":
    case "failed":
      return "progress";
    case "review":
    case "applying":
      return "review";
    default:
      return "list";
  }
}

type StatusFilter = "active" | "review" | "all";

const FILTER_LABELS: { key: StatusFilter; label: string }[] = [
  { key: "active", label: "Active" },
  { key: "review", label: "Review" },
  { key: "all", label: "All" },
];

const ACTIVE_STATUSES: MigrationJobStatus[] = [
  "pending",
  "migrating",
  "failed",
];
const REVIEW_STATUSES: MigrationJobStatus[] = ["review", "applying"];

function filterJobs(
  jobs: MigrationJob[],
  filter: StatusFilter,
): MigrationJob[] {
  if (filter === "active") {
    return jobs.filter((j) => ACTIVE_STATUSES.includes(j.status));
  }
  if (filter === "review") {
    return jobs.filter((j) => REVIEW_STATUSES.includes(j.status));
  }
  return jobs;
}

function basename(path: string): string {
  const parts = path.replace(/\/+$/, "").split("/");
  return (parts[parts.length - 1] || path) + "/";
}

export function MigrationDashboard() {
  const [step, setStep] = useState<Step>("list");
  const [taxonomy, setTaxonomy] = useState<TaxonomyProposal | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [targetVault, setTargetVault] = useState("");
  const [jsonInput, setJsonInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [model, setModel] = useState<"haiku" | "sonnet">("sonnet");
  const [jobs, setJobs] = useState<MigrationJob[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");

  // Sync jobId to localStorage
  const setJobIdWithStorage = useCallback((id: string | null) => {
    setJobId(id);
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (step !== "list") return;
    let mounted = true;
    (async () => {
      setListLoading(true);
      try {
        const { jobs: all } = await fetchMigrationJobs({ limit: 50 });
        if (mounted) setJobs(all);
      } catch {
        /* stay empty */
      } finally {
        if (mounted) setListLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [step]);

  function backToList() {
    setJobId(null);
    setTaxonomy(null);
    setCostEstimate(null);
    setStep("list");
    setError(null);
  }

  async function openJob(job: MigrationJob) {
    setJobIdWithStorage(job.id);
    setStep(stepFromStatus(job.status));
    if (job.taxonomy_id) {
      try {
        const t = await fetchTaxonomy(job.taxonomy_id);
        setTaxonomy(t);
      } catch {
        /* best effort */
      }
    }
  }

  async function handleImport() {
    setError(null);
    setLoading(true);
    try {
      const data = JSON.parse(jsonInput);
      const t = await importTaxonomy(data);
      setTaxonomy(t);
      setStep("taxonomy");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleEstimateCost() {
    setError(null);
    try {
      const est = await estimateMigrationCost(model, taxonomy?.id);
      setCostEstimate(est);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSaveTaxonomy(updates: Partial<TaxonomyProposal>) {
    if (!taxonomy) return;
    const updated = await updateTaxonomy(taxonomy.id, updates);
    setTaxonomy(updated);
  }

  async function handleActivateAndStart() {
    if (!taxonomy) return;
    if (!targetVault) {
      setError("Target vault path is required before starting migration");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await activateTaxonomy(taxonomy.id);
      const job = await createMigrationJob(targetVault, taxonomy.id, model);
      setJobIdWithStorage(job.id);
      setStep("progress");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleApplyComplete() {
    setJobIdWithStorage(null);
    setStep("list");
  }

  const filteredJobs = filterJobs(jobs, statusFilter);

  return (
    <div
      className={`flex flex-col gap-6 ${step === "review" || step === "progress" ? "" : "max-w-6xl"}`}
    >
      <div className="flex items-center gap-4">
        {step !== "list" && (
          <button
            onClick={backToList}
            className="text-muted hover:text-text text-sm cursor-pointer bg-transparent border-none"
          >
            &larr; Jobs
          </button>
        )}
        <h2 className="text-lg font-semibold">Vault Migration</h2>
        {step === "list" && (
          <button
            onClick={() => setStep("setup")}
            className="ml-auto bg-accent text-crust text-sm font-medium rounded px-4 py-2 cursor-pointer"
          >
            New Migration
          </button>
        )}
        {step !== "list" && (
          <div className="flex gap-1 ml-auto">
            {(["setup", "taxonomy", "progress", "review"] as const).map(
              (s, i) => (
                <span
                  key={s}
                  className={`px-3 py-1 text-xs rounded ${
                    step === s
                      ? "bg-accent/15 text-accent font-medium"
                      : "text-muted"
                  }`}
                >
                  {i + 1}. {s.charAt(0).toUpperCase() + s.slice(1)}
                </span>
              ),
            )}
          </div>
        )}
      </div>

      {error && <ErrorAlert message={error} />}

      {step === "list" && (
        <div className="flex flex-col gap-4">
          {/* Filter tabs */}
          <div className="flex gap-2">
            {FILTER_LABELS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setStatusFilter(key)}
                className={`px-3 py-1 text-xs rounded-full cursor-pointer border transition-colors ${
                  statusFilter === key
                    ? "bg-accent/15 text-accent border-transparent"
                    : "bg-surface text-muted border-border"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Loading skeleton */}
          {listLoading && jobs.length === 0 && (
            <div className="flex flex-col gap-3">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="bg-surface border border-border rounded-lg p-4 space-y-2"
                >
                  <Skeleton w="w-1/3" h="h-3" />
                  <Skeleton w="w-2/3" h="h-3" />
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {!listLoading && filteredJobs.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <p className="text-sm text-muted">No migration jobs found</p>
              <p className="text-xs text-muted/60">
                Start a new migration to reorganize your vault
              </p>
            </div>
          )}

          {/* Job cards */}
          {filteredJobs.length > 0 && (
            <div className="flex flex-col gap-3">
              {filteredJobs.map((job) => {
                const pct =
                  job.total_notes > 0
                    ? Math.round((job.processed_notes / job.total_notes) * 100)
                    : 0;
                return (
                  <div
                    key={job.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openJob(job)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openJob(job);
                      }
                    }}
                    className="bg-surface border border-border rounded-lg p-4 cursor-pointer hover:border-accent transition-colors focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex flex-col gap-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-muted truncate">
                            {job.id.slice(0, 8)}
                          </span>
                          <StatusBadge status={job.status} />
                        </div>
                        <span className="text-xs text-muted truncate">
                          {basename(job.source_vault)}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent">
                          {job.processed_notes}/{job.total_notes} notes
                        </span>
                        <div className="w-[60px] h-1.5 bg-base rounded-full overflow-hidden">
                          <div
                            className="h-full bg-accent rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        {job.estimated_cost_usd != null && (
                          <span className="text-xs text-muted">
                            ${job.estimated_cost_usd.toFixed(2)}
                          </span>
                        )}
                        <span className="text-xs text-muted">
                          {new Date(job.created_at).toLocaleDateString()}
                        </span>
                        {job.batch_mode && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-400">
                            batch
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {step === "setup" && (
        <div className="flex flex-col gap-4">
          <div>
            <label className="block text-sm text-muted mb-1">
              Target Vault Path
            </label>
            <input
              type="text"
              value={targetVault}
              onChange={(e) => setTargetVault(e.target.value)}
              placeholder="~/Documents/post-migration-vault"
              className="w-full px-3 py-2 bg-base border border-border rounded text-sm"
            />
          </div>

          <div>
            <label className="block text-sm text-muted mb-1">
              Taxonomy JSON (from Claude Code)
            </label>
            <textarea
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              rows={12}
              placeholder='{"folders": [...], "tag_hierarchy": [...], "link_targets": [...]}'
              className="w-full px-3 py-2 bg-base border border-border rounded text-sm font-mono"
            />
          </div>

          <div className="flex gap-3 items-center">
            <button
              onClick={handleImport}
              disabled={!jsonInput.trim() || loading}
              className="px-4 py-2 text-sm font-medium rounded bg-accent text-base disabled:opacity-50"
            >
              {loading ? "Importing..." : "Import Taxonomy"}
            </button>
            <button
              onClick={handleEstimateCost}
              className="px-4 py-2 text-sm font-medium rounded border border-border text-muted"
            >
              Estimate Cost
            </button>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value as "haiku" | "sonnet")}
              className="bg-surface border border-border rounded px-2 py-2 text-xs text-foreground outline-none focus:border-accent cursor-pointer"
            >
              <option value="haiku">Haiku 4.5</option>
              <option value="sonnet">Sonnet 4.6</option>
            </select>
          </div>

          {costEstimate && (
            <div className="p-4 bg-surface border border-border rounded text-sm">
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <span className="text-muted">Notes:</span>{" "}
                  {costEstimate.total_notes}
                </div>
                <div>
                  <span className="text-muted">Est. tokens:</span>{" "}
                  {(
                    costEstimate.estimated_input_tokens +
                    costEstimate.estimated_output_tokens
                  ).toLocaleString()}
                </div>
                <div>
                  <span className="text-muted">Est. cost:</span>{" "}
                  <span className="text-muted line-through mr-1">
                    ${costEstimate.estimated_cost_usd.toFixed(2)}
                  </span>
                  <span className="text-green font-medium">
                    ${costEstimate.batch_estimated_cost_usd.toFixed(2)}
                  </span>
                  <span className="text-muted text-xs ml-1">with batch</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {step === "taxonomy" && taxonomy && (
        <TaxonomyEditor
          taxonomy={taxonomy}
          onSave={handleSaveTaxonomy}
          onActivate={handleActivateAndStart}
        />
      )}

      {step === "progress" && jobId && (
        <MigrationProgress
          jobId={jobId}
          model={model}
          onReviewReady={() => setStep("review")}
        />
      )}

      {step === "review" && jobId && (
        <MigrationNoteReview jobId={jobId} onApply={handleApplyComplete} />
      )}
    </div>
  );
}
