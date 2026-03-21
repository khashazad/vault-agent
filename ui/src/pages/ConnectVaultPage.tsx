import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import {
  openVaultPicker,
  fetchVaultHistory,
  deleteVaultHistory,
} from "../api/client";
import { useVault } from "../context/VaultContext";
import type { VaultHistoryEntry } from "../types";

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function shortenPath(path: string): string {
  const home = path.match(/^\/Users\/[^/]+/)?.[0];
  return home ? path.replace(home, "~") : path;
}

export function ConnectVaultPage() {
  const navigate = useNavigate();
  const { setVault } = useVault();

  const [history, setHistory] = useState<VaultHistoryEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetchVaultHistory();
      setHistory(res.vaults);
    } catch {
      // history unavailable — not critical
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleConnect = async (path: string) => {
    setConnecting(path);
    setError(null);
    try {
      await setVault(path);
      navigate("/library");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to connect vault");
    } finally {
      setConnecting(null);
    }
  };

  const handlePicker = async () => {
    setPicking(true);
    setError(null);
    try {
      const res = await openVaultPicker();
      if (res.cancelled || !res.path) {
        return;
      }
      await handleConnect(res.path);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to open folder picker");
    } finally {
      setPicking(false);
    }
  };

  const handleRemoveHistory = async (path: string) => {
    try {
      await deleteVaultHistory(path);
      setHistory((prev) => prev.filter((v) => v.path !== path));
    } catch {
      // silent fail
    }
  };

  return (
    <div className="relative min-h-screen bg-bg overflow-hidden">
      {/* Decorative blurs */}
      <div className="absolute top-[-120px] left-[-80px] w-[400px] h-[400px] rounded-full bg-[#cba6f7]/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-100px] right-[-60px] w-[350px] h-[350px] rounded-full bg-[#89b4fa]/10 blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="h-14 flex items-center justify-between px-6 border-b border-border/50">
        <span className="text-sm font-semibold text-text">Vault Agent</span>
      </header>

      {/* Main content */}
      <div className="max-w-xl mx-auto px-8 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text mb-2">Open Vault</h1>
          <p className="text-sm text-muted leading-relaxed">
            Select an Obsidian vault to connect
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-[#f38ba8]/10 border border-[#f38ba8]/30 text-sm text-[#f38ba8]">
            {error}
          </div>
        )}

        {/* Browse button */}
        <button
          onClick={handlePicker}
          disabled={picking || connecting !== null}
          className="btn-gradient w-full py-3 text-sm font-medium mb-8"
        >
          {picking ? "Waiting for folder selection..." : "Browse for Vault..."}
        </button>

        {/* Recent vaults */}
        <div className="mb-3 flex items-center gap-3">
          <span className="text-xs font-semibold text-muted uppercase tracking-wider">
            Recent Vaults
          </span>
          <div className="flex-1 h-px bg-border/50" />
        </div>

        {loadingHistory ? (
          <div className="glass-card px-4 py-8 text-center text-sm text-muted">
            Loading...
          </div>
        ) : history.length === 0 ? (
          <div className="glass-card px-4 py-8 text-center text-sm text-muted">
            No previously opened vaults
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {history.map((vault) => (
              <div
                key={vault.path}
                className="glass-card flex items-center gap-3 px-4 py-3 hover:bg-elevated/50 transition-colors group"
              >
                {/* Vault icon */}
                <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                  <span className="text-accent text-sm font-bold">
                    {vault.name.charAt(0).toUpperCase()}
                  </span>
                </div>

                {/* Info — clickable */}
                <button
                  onClick={() => handleConnect(vault.path)}
                  disabled={connecting !== null}
                  className="flex-1 text-left bg-transparent border-none cursor-pointer p-0 min-w-0"
                >
                  <div className="text-sm font-medium text-text truncate">
                    {vault.name}
                  </div>
                  <div className="text-xs text-muted truncate">
                    {shortenPath(vault.path)}
                  </div>
                  <div className="text-[11px] text-muted/60 mt-0.5">
                    {relativeTime(vault.last_opened)}
                  </div>
                </button>

                {connecting === vault.path && (
                  <span className="text-xs text-accent shrink-0">
                    Connecting...
                  </span>
                )}

                {/* Remove button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveHistory(vault.path);
                  }}
                  className="opacity-0 group-hover:opacity-100 bg-transparent border-none cursor-pointer p-1 text-muted hover:text-[#f38ba8] transition-all shrink-0"
                  title="Remove from history"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
