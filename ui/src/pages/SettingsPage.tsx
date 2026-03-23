import { useState, useEffect, useCallback } from "react";
import type { ClawdyConfig } from "../types";
import {
  fetchClawdyConfig,
  updateClawdyConfig,
  openVaultPicker,
} from "../api/client";
import { formatError } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { Skeleton } from "../components/Skeleton";

const SECTIONS = [{ id: "clawdy", label: "Clawdy Inbox" }] as const;

const INTERVAL_OPTIONS = [
  { value: 60, label: "1 min" },
  { value: 300, label: "5 min" },
  { value: 900, label: "15 min" },
  { value: 1800, label: "30 min" },
];

function SettingsSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton h="h-5" w="w-32" />
      <div className="flex flex-col gap-4">
        <Skeleton h="h-4" w="w-24" />
        <Skeleton h="h-9" w="w-full" />
      </div>
      <div className="flex items-center justify-between">
        <Skeleton h="h-4" w="w-32" />
        <Skeleton h="h-5" w="w-9" className="rounded-full" />
      </div>
      <div className="flex items-center justify-between">
        <Skeleton h="h-4" w="w-24" />
        <Skeleton h="h-8" w="w-24" />
      </div>
    </div>
  );
}

function ClawdySettings({
  config,
  onUpdate,
  error,
}: {
  config: ClawdyConfig;
  onUpdate: (patch: Partial<ClawdyConfig>) => Promise<void>;
  error: string | null;
}) {
  const [picking, setPicking] = useState(false);

  async function handleBrowse() {
    setPicking(true);
    try {
      const res = await openVaultPicker();
      if (!res.cancelled && res.path) {
        await onUpdate({ copy_vault_path: res.path });
      }
    } finally {
      setPicking(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h3 className="text-sm font-semibold m-0">Clawdy Inbox</h3>

      {error && <ErrorAlert message={error} />}

      {/* Copy vault path */}
      <div className="flex flex-col gap-2">
        <span className="text-xs text-muted">Copy Vault Path</span>
        <div className="flex items-center gap-3">
          <span className="flex-1 text-xs font-mono text-text bg-elevated border border-border rounded px-3 py-2 truncate">
            {config.copy_vault_path || "Not configured"}
          </span>
          <button
            onClick={handleBrowse}
            disabled={picking}
            className="text-xs px-3 py-2 rounded bg-accent/15 text-accent border-none cursor-pointer hover:bg-accent/25 disabled:opacity-50 shrink-0"
          >
            {picking ? "Selecting..." : "Browse"}
          </button>
        </div>
      </div>

      {/* Enable polling */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-text">Enable polling</div>
          <div className="text-[11px] text-muted mt-0.5">
            Periodically check the copy vault for changes
          </div>
        </div>
        <button
          role="switch"
          aria-checked={config.enabled}
          aria-label="Enable polling"
          onClick={() => onUpdate({ enabled: !config.enabled })}
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer border-none ${
            config.enabled ? "bg-green" : "bg-elevated"
          }`}
        >
          <span
            className={`inline-block h-3.5 w-3.5 rounded-full bg-text transition-transform ${
              config.enabled ? "translate-x-4.5" : "translate-x-0.5"
            }`}
          />
        </button>
      </div>

      {/* Poll interval */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-text">Poll interval</div>
          <div className="text-[11px] text-muted mt-0.5">
            How often to check for changes
          </div>
        </div>
        <select
          id="poll-interval"
          aria-label="Poll interval"
          value={config.interval}
          onChange={(e) => onUpdate({ interval: Number(e.target.value) })}
          className="text-xs bg-elevated border border-border rounded px-2 py-1.5 text-text cursor-pointer"
        >
          {INTERVAL_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

export function SettingsPage() {
  const [activeSection, setActiveSection] =
    useState<(typeof SECTIONS)[number]["id"]>("clawdy");
  const [config, setConfig] = useState<ClawdyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await fetchClawdyConfig();
      setConfig(cfg);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleUpdate = useCallback(async (patch: Partial<ClawdyConfig>) => {
    setError(null);
    try {
      const updated = await updateClawdyConfig(patch);
      setConfig(updated);
    } catch (err) {
      setError(formatError(err));
    }
  }, []);

  return (
    <div className="flex h-full">
      {/* Section sidebar */}
      <div className="w-[200px] shrink-0 border-r border-border/30 py-6 px-3">
        <div className="text-[10px] text-muted uppercase tracking-wide font-semibold px-3 mb-2">
          Settings
        </div>
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveSection(s.id)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors ${
              activeSection === s.id
                ? "bg-purple/10 text-purple font-medium border-l-2 border-purple border-y-0 border-r-0"
                : "bg-transparent text-muted hover:text-text hover:bg-elevated/50 border-none"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Settings panel */}
      <div className="flex-1 py-6 px-8 overflow-auto">
        {activeSection === "clawdy" && (
          <>
            {loading ? (
              <SettingsSkeleton />
            ) : config ? (
              <ClawdySettings
                config={config}
                onUpdate={handleUpdate}
                error={error}
              />
            ) : (
              <ErrorAlert message={error || "Failed to load settings"} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
