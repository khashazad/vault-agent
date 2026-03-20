import { useState, useEffect, useCallback } from "react";
import type { TaxonomyProposal, CostEstimate, MigrationJob } from "../types";
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

type Step = "setup" | "taxonomy" | "progress" | "review";

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
      return "setup";
  }
}

export function MigrationDashboard() {
  const [step, setStep] = useState<Step>("setup");
  const [taxonomy, setTaxonomy] = useState<TaxonomyProposal | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [targetVault, setTargetVault] = useState("");
  const [jsonInput, setJsonInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [reconnecting, setReconnecting] = useState(true);
  const [model, setModel] = useState<"haiku" | "sonnet">("sonnet");

  // Auto-detect active job on mount
  useEffect(() => {
    async function reconnect() {
      try {
        const { jobs } = await fetchMigrationJobs({ limit: 5 });
        const active = jobs.find((j) =>
          ["pending", "migrating", "review", "applying", "failed"].includes(
            j.status,
          ),
        );
        if (active) {
          setJobId(active.id);
          setStep(stepFromStatus(active.status));
          localStorage.setItem(STORAGE_KEY, active.id);
          // Load taxonomy if available
          if (active.taxonomy_id) {
            try {
              const t = await fetchTaxonomy(active.taxonomy_id);
              setTaxonomy(t);
            } catch {
              // taxonomy load is best-effort
            }
          }
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      } catch {
        // API not available, stay on setup
      } finally {
        setReconnecting(false);
      }
    }
    reconnect();
  }, []);

  // Sync jobId to localStorage
  const setJobIdWithStorage = useCallback((id: string | null) => {
    setJobId(id);
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

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
    setStep("setup");
  }

  if (reconnecting) {
    return (
      <div className="text-muted text-sm p-4">
        Checking for active migration...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-6xl">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold">Vault Migration</h2>
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
      </div>

      {error && <ErrorAlert message={error} />}

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
