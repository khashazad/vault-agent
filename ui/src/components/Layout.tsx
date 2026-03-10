import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
}

export function Layout({ children }: Props) {
  return (
    <div className="flex flex-col h-screen">
      <header className="h-12 bg-surface border-b border-border shrink-0">
        <div className="flex items-center px-6 h-full">
          <span className="text-base font-semibold">Vault Agent</span>
        </div>
      </header>
      <main className="flex-1 overflow-y-auto py-6 px-8">
        {children}
      </main>
    </div>
  );
}
