import { useNavigate } from "react-router";

export function ConnectVaultPage() {
  const navigate = useNavigate();

  return (
    <div className="relative min-h-screen bg-bg overflow-hidden">
      {/* Decorative blurs */}
      <div className="absolute top-[-120px] left-[-80px] w-[400px] h-[400px] rounded-full bg-[#cba6f7]/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-100px] right-[-60px] w-[350px] h-[350px] rounded-full bg-[#89b4fa]/10 blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="h-14 flex items-center justify-between px-6 border-b border-border/50">
        <span className="text-sm font-semibold text-text">Vault Agent</span>
        <button
          onClick={() => navigate("/library")}
          className="text-muted hover:text-text bg-transparent border-none cursor-pointer"
          aria-label="Settings"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
      </header>

      {/* Main content */}
      <div className="max-w-5xl mx-auto px-8 py-12 grid grid-cols-1 md:grid-cols-2 gap-10">
        {/* Left column */}
        <div className="flex flex-col gap-6">
          <div>
            <h1 className="text-2xl font-bold text-text mb-2">Connect Vault</h1>
            <p className="text-sm text-muted leading-relaxed">
              Link your Obsidian vault to enable AI-powered annotation
              synthesis, migration tooling, and taxonomy management.
            </p>
          </div>

          {/* Dropzone placeholder */}
          <div className="border-2 border-dashed border-border rounded-xl p-10 flex flex-col items-center gap-3 hover:border-accent/50 transition-colors cursor-pointer">
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-muted"
            >
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <span className="text-sm text-muted">
              Drop vault folder here or click to browse
            </span>
            <span className="text-[10px] text-muted/60">
              Must contain .obsidian/ directory
            </span>
          </div>

          {/* Current selection card */}
          <div className="glass-card p-4 flex flex-col gap-2">
            <span className="text-[10px] text-muted uppercase tracking-wide">
              Current Selection
            </span>
            <div className="flex items-center gap-2">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-accent"
              >
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
              <span className="text-sm font-medium text-text">My Vault</span>
            </div>
            <span className="text-xs font-mono text-muted">
              ~/Documents/obsidian-vault
            </span>
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-6">
          {/* Quick tips */}
          <div className="glass-card p-5 flex flex-col gap-3">
            <h3 className="text-sm font-semibold text-text">Quick Tips</h3>
            <ul className="flex flex-col gap-2 text-xs text-muted list-none m-0 p-0">
              <li className="flex gap-2">
                <span className="text-accent">1.</span>
                Point to a vault with existing notes for best results
              </li>
              <li className="flex gap-2">
                <span className="text-accent">2.</span>
                The vault map helps the AI understand your note structure
              </li>
              <li className="flex gap-2">
                <span className="text-accent">3.</span>
                All writes are additive-only — nothing gets deleted
              </li>
            </ul>
          </div>

          {/* Quote */}
          <div className="glass-card p-5">
            <blockquote className="text-sm text-muted italic m-0 border-l-2 border-accent pl-3">
              "The best note-taking system is the one you actually use."
            </blockquote>
          </div>

          {/* CTA */}
          <button
            onClick={() => navigate("/library")}
            className="btn-gradient flex items-center justify-center gap-2 w-full"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
              <polyline points="10 17 15 12 10 7" />
              <line x1="15" x2="3" y1="12" y2="12" />
            </svg>
            Initialize Workspace
          </button>
        </div>
      </div>
    </div>
  );
}
