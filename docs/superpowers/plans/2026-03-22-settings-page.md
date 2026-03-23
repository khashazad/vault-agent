# Settings Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Obsidian-style settings page with Clawdy Inbox configuration, replacing inline config controls on ClawdyInboxPage.

**Architecture:** New `/settings` route with two-panel layout (section sidebar + settings panel). Gear icon in app sidebar footer navigates to it. ClawdyInboxPage simplified to status-only bar. No backend changes — existing endpoints suffice.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4 (Catppuccin Mocha)

**Spec:** `docs/superpowers/specs/2026-03-22-settings-page-design.md`

---

## Task 1: Create SettingsPage

**Files:**
- Create: `ui/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Create SettingsPage with two-panel layout and Clawdy settings**

Create `ui/src/pages/SettingsPage.tsx`:

```tsx
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
```

- [ ] **Step 2: Run frontend tests for regressions**

Run: `cd ui && bun run test`
Expected: PASS (no test changes, existing tests unaffected)

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/SettingsPage.tsx
git commit -m "feat: add SettingsPage with Clawdy Inbox configuration"
```

---

## Task 2: Add Route and Sidebar Gear Icon

**Files:**
- Modify: `ui/src/router.tsx`
- Modify: `ui/src/components/Sidebar.tsx`

- [ ] **Step 1: Add /settings route to router.tsx**

In `ui/src/router.tsx`, add import:

```typescript
import { SettingsPage } from "./pages/SettingsPage";
```

Add to children array after the clawdy route:

```typescript
{ path: "settings", element: <SettingsPage /> },
```

- [ ] **Step 2: Add gear icon to Sidebar footer**

In `ui/src/components/Sidebar.tsx`, replace the spacer + footer section (lines 223-234):

Replace:
```tsx
      {/* Spacer when not on library route */}
      {!isLibraryRoute && <div className="flex-1" />}

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border/30">
```

With:
```tsx
      {/* Spacer when not on library route */}
      {!isLibraryRoute && <div className="flex-1" />}

      {/* Settings gear */}
      <div className="px-5 py-2">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-2.5 text-sm no-underline transition-colors ${
              isActive
                ? "text-purple"
                : "text-muted hover:text-text"
            }`
          }
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
          Settings
        </NavLink>
      </div>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-border/30">
```

- [ ] **Step 3: Run frontend tests**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ui/src/router.tsx ui/src/components/Sidebar.tsx
git commit -m "feat: add /settings route and gear icon to sidebar"
```

---

## Task 3: Simplify ClawdyInboxPage to Status-Only

**Files:**
- Modify: `ui/src/pages/ClawdyInboxPage.tsx`

- [ ] **Step 1: Replace ClawdyInboxPage config bar with slim status line**

Replace the entire contents of `ui/src/pages/ClawdyInboxPage.tsx` with:

```tsx
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import type { ChangesetSummary, ClawdyStatus } from "../types";
import {
  fetchClawdyStatus,
  triggerClawdySync,
  fetchChangesets,
} from "../api/client";
import { formatError } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { StatusBadge } from "../components/StatusBadge";
import { Pagination } from "../components/Pagination";
import { Skeleton } from "../components/Skeleton";

const PAGE_SIZE = 25;

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }, (_, i) => (
        <div
          key={i}
          className="bg-surface border border-border rounded p-4 flex flex-col gap-2"
        >
          <div className="flex items-center gap-2">
            <Skeleton h="h-3" w="w-20" />
            <Skeleton h="h-4" w="w-16" className="rounded-full" />
          </div>
          <Skeleton h="h-3" w="w-2/5" />
        </div>
      ))}
    </div>
  );
}

export function ClawdyInboxPage() {
  const navigate = useNavigate();

  const [status, setStatus] = useState<ClawdyStatus | null>(null);
  const [summaries, setSummaries] = useState<ChangesetSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);

  const [statusLoading, setStatusLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const st = await fetchClawdyStatus();
      setStatus(st);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setStatusLoading(false);
    }
  }, []);

  const loadChangesets = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await fetchChangesets({
        source_type: "clawdy",
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setSummaries(res.changesets);
      setTotal(res.total);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setListLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    loadChangesets();
  }, [loadChangesets]);

  async function handleCheckNow() {
    setSyncing(true);
    setError(null);
    try {
      await triggerClawdySync();
      const st = await fetchClawdyStatus();
      setStatus(st);
      await loadChangesets();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSyncing(false);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex flex-col gap-4 py-6 px-8">
      <h2 className="text-base font-semibold m-0">Clawdy Inbox</h2>

      {error && <ErrorAlert message={error} />}

      {/* Status line */}
      {statusLoading ? (
        <div className="flex items-center gap-4">
          <Skeleton h="h-3" w="w-16" />
          <Skeleton h="h-3" w="w-32" />
          <Skeleton h="h-6" w="w-20" />
        </div>
      ) : status ? (
        <div className="flex items-center gap-4 flex-wrap text-xs text-muted">
          <span className={status.enabled ? "text-green" : "text-muted"}>
            {status.enabled ? "Enabled" : "Disabled"}
          </span>
          {status.last_poll && (
            <span>
              Last poll: {new Date(status.last_poll).toLocaleString()}
            </span>
          )}
          {status.pending_changeset_count > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-yellow/15 text-yellow">
              {status.pending_changeset_count} pending
            </span>
          )}
          {status.last_error && (
            <span className="text-red truncate max-w-md">
              Error: {status.last_error}
            </span>
          )}
          <button
            onClick={handleCheckNow}
            disabled={syncing}
            className="text-xs px-3 py-1.5 rounded bg-accent/15 text-accent border-none cursor-pointer hover:bg-accent/25 disabled:opacity-50"
          >
            {syncing ? "Checking..." : "Check Now"}
          </button>
        </div>
      ) : null}

      {/* Changeset list */}
      {listLoading && summaries.length === 0 ? (
        <ListSkeleton />
      ) : summaries.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <span className="text-sm text-muted">No clawdy changesets yet.</span>
          <span className="text-xs text-muted/70">
            Changes from OpenClaw will appear here after polling
          </span>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-2">
            {summaries.map((cs) => (
              <div
                key={cs.id}
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/changesets/${cs.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ")
                    navigate(`/changesets/${cs.id}`);
                }}
                className="bg-surface border border-border rounded p-4 text-left cursor-pointer hover:border-accent transition-colors w-full focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex flex-col gap-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-muted truncate">
                        {cs.id.slice(0, 8)}...
                      </span>
                      <StatusBadge status={cs.status} />
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface border border-border text-muted">
                        {cs.source_type}
                      </span>
                    </div>
                    {cs.routing?.target_path && (
                      <span className="text-xs text-muted truncate">
                        {cs.routing.action} &rarr; {cs.routing.target_path}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent">
                      {cs.change_count} change
                      {cs.change_count !== 1 ? "s" : ""}
                    </span>
                    <span className="text-xs text-muted">
                      {new Date(cs.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            totalItems={total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
```

Key changes from original:
- Removed: `ClawdyConfig` type import, `fetchClawdyConfig`, `updateClawdyConfig` imports
- Removed: `INTERVAL_OPTIONS`, `ConfigSkeleton`, config state, `configLoading`, `handleToggleEnabled`, `handleIntervalChange`
- Removed: entire config/status bar section (toggle, interval dropdown, copy vault path display)
- Added: slim status line with enabled indicator, last poll, pending count, error, Check Now button
- Kept: changeset list, pagination, ListSkeleton, handleCheckNow unchanged

- [ ] **Step 2: Run frontend tests**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/ClawdyInboxPage.tsx
git commit -m "refactor: simplify ClawdyInboxPage to status-only bar"
```

---

## Task 4: Run Full Test Suite and Update Docs

**Files:**
- Modify: `CLAUDE.md` — add `/settings` to router structure, add `SettingsPage` to pages list

- [ ] **Step 1: Run all frontend tests**

Run: `cd ui && bun run test`
Expected: PASS (85 tests)

- [ ] **Step 2: Run all backend tests**

Run: `uv run pytest tests/ -v`
Expected: PASS (218 tests)

- [ ] **Step 3: TypeScript type check**

Run: `cd ui && npx tsc -b --noEmit`
Expected: clean, no errors

- [ ] **Step 4: Update CLAUDE.md router structure**

In `CLAUDE.md`, add to the router structure section after the clawdy route:

```
  /settings        → SettingsPage (app settings: Clawdy Inbox config)
```

Add to the Pages section:

```
- **`SettingsPage`** — Obsidian-style settings with section sidebar; Clawdy config (copy vault path, polling toggle, interval)
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add settings page to CLAUDE.md"
```
