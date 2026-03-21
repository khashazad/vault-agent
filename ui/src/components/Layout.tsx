import type { ReactNode } from "react";
import { Navigate } from "react-router";
import { Sidebar } from "./Sidebar";
import { useVault } from "../context/VaultContext";

interface Props {
  children: ReactNode;
}

export function Layout({ children }: Props) {
  const { vaultPath, isLoading } = useVault();

  if (isLoading) {
    return (
      <div className="flex h-screen bg-bg items-center justify-center">
        <span className="text-sm text-muted">Loading...</span>
      </div>
    );
  }

  if (!vaultPath) {
    return <Navigate to="/connect" replace />;
  }

  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 overflow-y-auto flex flex-col">{children}</main>
      </div>
    </div>
  );
}
