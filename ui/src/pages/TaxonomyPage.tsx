import { useState } from "react";

type Tab = "folders" | "tags" | "links";

const SAMPLE_FOLDERS = [
  "Papers/",
  "Notes/Research/",
  "Notes/Daily/",
  "References/",
  "Projects/vault-agent/",
  "Archive/2024/",
];

const SAMPLE_TAGS = [
  {
    name: "#research",
    children: ["#research/ai", "#research/ml", "#research/nlp"],
  },
  {
    name: "#biology",
    children: ["#biology/genomics", "#biology/neuroscience"],
  },
  { name: "#projects", children: ["#projects/vault-agent"] },
];

const SAMPLE_LINKS = [
  { title: "Transformer Architecture", aliases: ["Attention Mechanism"] },
  { title: "Backpropagation", aliases: ["Backprop", "BP"] },
  {
    title: "Gradient Descent",
    aliases: ["SGD", "Stochastic Gradient Descent"],
  },
];

export function TaxonomyPage() {
  const [tab, setTab] = useState<Tab>("folders");

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
          Taxonomy Management
        </h2>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-surface rounded-lg p-1 self-start">
        {(["folders", "tags", "links"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer border-none ${
              tab === t
                ? "bg-accent/15 text-accent"
                : "bg-transparent text-muted hover:text-text"
            }`}
          >
            {t === "folders"
              ? "Folders"
              : t === "tags"
                ? "Tags"
                : "Link Targets"}
          </button>
        ))}
      </div>

      {/* Bento grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Registered paths / Tags / Links — depends on tab */}
        <div className="glass-card p-4 flex flex-col gap-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
            {tab === "folders"
              ? "Registered Paths"
              : tab === "tags"
                ? "Tag Hierarchy"
                : "Canonical Link Targets"}
          </h3>

          {tab === "folders" && (
            <div className="flex flex-col gap-1.5">
              {SAMPLE_FOLDERS.map((f) => (
                <div
                  key={f}
                  className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-elevated/50 transition-colors"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-accent flex-shrink-0"
                  >
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                  <span className="text-xs font-mono text-text">{f}</span>
                </div>
              ))}
            </div>
          )}

          {tab === "tags" && (
            <div className="flex flex-col gap-2">
              {SAMPLE_TAGS.map((t) => (
                <div key={t.name} className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-text">
                    {t.name}
                  </span>
                  <div className="pl-4 flex flex-col gap-0.5">
                    {t.children.map((c) => (
                      <span
                        key={c}
                        className="text-[11px] font-mono text-muted"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "links" && (
            <div className="flex flex-col gap-2">
              {SAMPLE_LINKS.map((l) => (
                <div
                  key={l.title}
                  className="bg-elevated/30 rounded-lg p-3 flex flex-col gap-1"
                >
                  <span className="text-xs font-medium text-text">
                    {l.title}
                  </span>
                  <span className="text-[10px] text-muted">
                    Aliases: {l.aliases.join(", ")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Archive Health */}
        <div className="flex flex-col gap-4">
          <div className="glass-card p-4 flex flex-col gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
              Archive Health
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="stat-value">142</span>
                <span className="block text-[10px] text-muted mt-1">
                  Unique Folders
                </span>
              </div>
              <div>
                <span className="stat-value text-yellow">3</span>
                <span className="block text-[10px] text-muted mt-1">
                  Orphaned Nodes
                </span>
              </div>
            </div>
          </div>

          {/* Hierarchy Optimizer */}
          <div className="glass-card p-4 flex flex-col gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
              Hierarchy Optimizer
            </h3>
            <p className="text-xs text-muted m-0">
              Analyze your taxonomy for redundancies, missing links, and
              optimization opportunities.
            </p>
            <button className="btn-gradient self-start text-xs py-2 px-4">
              Start Analysis
            </button>
          </div>
        </div>
      </div>

      {/* FAB */}
      <button className="fab" aria-label="Add new item">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        >
          <line x1="12" x2="12" y1="5" y2="19" />
          <line x1="5" x2="19" y1="12" y2="12" />
        </svg>
      </button>
    </div>
  );
}
