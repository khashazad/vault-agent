import { useState } from "react";
import type { TaxonomyProposal, CostEstimate } from "../types";
import {
  importTaxonomy,
  updateTaxonomy,
  activateTaxonomy,
  estimateMigrationCost,
  createMigrationJob,
} from "../api/client";
import { TaxonomyEditor } from "./TaxonomyEditor";
import { MigrationProgress } from "./MigrationProgress";
import { MigrationNoteReview } from "./MigrationNoteReview";
import { ErrorAlert } from "./ErrorAlert";

type Step = "setup" | "taxonomy" | "progress" | "review";

export function MigrationDashboard() {
  const [step, setStep] = useState<Step>("setup");
  const [taxonomy, setTaxonomy] = useState<TaxonomyProposal | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [targetVault, setTargetVault] = useState("");
  const [jsonInput, setJsonInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      const est = await estimateMigrationCost("sonnet");
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
      const job = await createMigrationJob(targetVault, taxonomy.id);
      setJobId(job.id);
      setStep("progress");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
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

          <div className="flex gap-3">
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
                  <span className="text-accent font-medium">
                    ${costEstimate.estimated_cost_usd.toFixed(2)}
                  </span>
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
          onReviewReady={() => setStep("review")}
        />
      )}

      {step === "review" && jobId && (
        <MigrationNoteReview jobId={jobId} onApply={() => setStep("setup")} />
      )}
    </div>
  );
}
