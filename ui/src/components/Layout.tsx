import type { ReactNode } from "react";

interface Props {
  activeView: string;
  onViewChange: (view: string) => void;
  children: ReactNode;
}

export function Layout({ activeView, onViewChange, children }: Props) {
  return (
    <div className="layout">
      <nav className="sidebar">
        <div className="sidebar-brand">Vault Agent</div>
        <div className="sidebar-nav">
          <button
            className={`nav-item ${activeView === "new" ? "active" : ""}`}
            onClick={() => onViewChange("new")}
          >
            + New Highlight
          </button>
          <button
            className={`nav-item ${activeView === "history" ? "active" : ""}`}
            onClick={() => onViewChange("history")}
          >
            History
          </button>
        </div>
      </nav>
      <main className="main-content">{children}</main>
    </div>
  );
}
