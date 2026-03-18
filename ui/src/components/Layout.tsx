import type { ReactNode } from "react";

export type Tab = "sync" | "history" | "migration";

interface Props {
  children: ReactNode;
  currentTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export function Layout({ children, currentTab, onTabChange }: Props) {
  return (
    <div className="flex flex-col h-screen">
      <header className="h-12 bg-surface border-b border-border shadow-sm shrink-0">
        <div className="flex items-center px-6 h-full">
          <span className="text-base font-semibold">Vault Agent</span>
          <div className="flex gap-2 ml-auto">
            {(["sync", "history", "migration"] as const).map((tab) => {
              const labels: Record<Tab, string> = {
                sync: "Sync",
                history: "History",
                migration: "Migration",
              };
              return (
                <button
                  key={tab}
                  onClick={() => onTabChange(tab)}
                  className={
                    currentTab === tab
                      ? "px-4 py-1.5 text-sm font-medium rounded bg-accent/15 text-accent"
                      : "px-4 py-1.5 text-sm font-medium rounded bg-surface text-muted border border-border"
                  }
                >
                  {labels[tab]}
                </button>
              );
            })}
          </div>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto py-6 px-8 flex flex-col">
        {children}
      </main>
    </div>
  );
}
