import type { ReactNode } from "react";

interface Props {
  activeView: string;
  onViewChange: (view: string) => void;
  children: ReactNode;
}

function NavButton({
  label,
  view,
  activeView,
  onViewChange,
}: {
  label: string;
  view: string;
  activeView: string;
  onViewChange: (view: string) => void;
}) {
  const isActive = activeView === view;
  return (
    <button
      className={`bg-transparent border-none text-muted py-2 px-3 text-left rounded text-sm cursor-pointer hover:bg-elevated hover:text-text ${isActive ? "bg-elevated !text-text font-medium" : ""}`}
      onClick={() => onViewChange(view)}
    >
      {label}
    </button>
  );
}

export function Layout({ activeView, onViewChange, children }: Props) {
  return (
    <div className="flex h-screen">
      <nav className="w-[220px] bg-surface border-r border-border flex flex-col py-4 shrink-0">
        <div className="text-base font-semibold px-4 pb-4 border-b border-border mb-2">
          Vault Agent
        </div>
        <div className="flex flex-col gap-0.5 px-2">
          <NavButton label="Preview" view="preview" activeView={activeView} onViewChange={onViewChange} />
          <NavButton label="Search" view="search" activeView={activeView} onViewChange={onViewChange} />
          <NavButton label="History" view="history" activeView={activeView} onViewChange={onViewChange} />
        </div>
      </nav>
      <main className="flex-1 overflow-y-auto py-6 px-8 max-w-[900px]">
        {children}
      </main>
    </div>
  );
}
