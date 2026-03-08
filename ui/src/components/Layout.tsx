import type { ReactNode } from "react";

interface Props {
  activeView: string;
  onViewChange: (view: string) => void;
  children: ReactNode;
}

const NAV_ITEMS = [
  { label: "Review", view: "preview" },
  { label: "Search", view: "search" },
  { label: "History", view: "history" },
  { label: "Zotero", view: "zotero" },
];

function NavButton({
  label,
  isActive,
  onClick,
}: {
  label: string;
  isActive: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`bg-transparent border-0 border-b-2 text-muted px-3 py-3 text-sm cursor-pointer hover:text-text ${isActive ? "border-accent !text-text font-medium" : "border-transparent"}`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}

export function Layout({ activeView, onViewChange, children }: Props) {
  return (
    <div className="flex flex-col h-screen">
      <header className="h-12 bg-surface border-b border-border shrink-0">
        <div className="flex items-center px-6 h-full">
          <span className="text-base font-semibold mr-8">Vault Agent</span>
          <nav className="flex gap-1">
            {NAV_ITEMS.map(({ label, view }) => (
              <NavButton
                key={view}
                label={label}
                isActive={activeView === view}
                onClick={() => onViewChange(view)}
              />
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto py-6 px-8">
        {children}
      </main>
    </div>
  );
}
