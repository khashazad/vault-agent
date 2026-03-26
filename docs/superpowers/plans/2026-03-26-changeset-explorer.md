# Changeset File Explorer & Clawdy Stacking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add changeset stacking for clawdy polls, a VS Code-style file explorer for multi-change review, and generalized convergence across all source types.

**Architecture:** Backend adds `merge_changes()` to ChangesetStore and removes the skip-if-pending gate in ClawdyService.poll(). Frontend extracts `useChangesetActions` hook from ChangesetReview, adds a FileExplorer tree component, and redesigns ChangesetDetailPage with a three-panel layout for multi-change sets. Convergence is generalized so any changeset syncs to copy vault when configured.

**Tech Stack:** Python/FastAPI/SQLite (backend), React 19/TypeScript/Tailwind CSS 4 (frontend), pytest + vitest (tests)

---

## File Structure

### New Files
- `ui/src/hooks/useChangesetActions.ts` — Extracted changeset mutation logic
- `ui/src/components/FileExplorer.tsx` — Folder tree with change badges

### Modified Files
- `src/models/changesets.py` — Add `updated_at` field to `Changeset` and `ChangesetSummary`
- `src/db/changesets.py` — Add `merge_changes()` method, migrate `updated_at` column
- `src/clawdy/service.py` — Remove skip-if-pending, call `merge_changes()`
- `src/server.py` — Generalize converge endpoint, expose `updated_at` in summary
- `ui/src/types.ts` — Add `updated_at` to `Changeset` and `ChangesetSummary`
- `ui/src/pages/ChangesetDetailPage.tsx` — Three-panel layout for multi-change
- `ui/src/components/ChangesetReview.tsx` — Simplified to single-change, uses hook
- `ui/src/api/client.ts` — Add `fetchClawdyConfig` usage note (already exists)

### Test Files
- `tests/unit/test_changeset_store.py` — New: tests for `merge_changes()`
- `tests/unit/test_clawdy_service.py` — Update: stacking behavior tests
- `ui/src/__tests__/components/FileExplorer.test.tsx` — New: FileExplorer tests
- `ui/src/__tests__/components/ChangesetReview.test.tsx` — Update for simplified component

---

## Task 1: Backend — `updated_at` Field

**Files:**
- Modify: `src/models/changesets.py:64-91` (Changeset model)
- Modify: `src/models/changesets.py:150-158` (ChangesetSummary model)
- Modify: `src/db/changesets.py:35-52` (migration method)

- [ ] **Step 1: Add `updated_at` to Changeset model**

In `src/models/changesets.py`, add the field after `created_at`:

```python
# In class Changeset, after line 75:
    created_at: str = Field(description="ISO 8601 creation timestamp")
    updated_at: str | None = Field(
        default=None, description="ISO 8601 last-updated timestamp, set by merge_changes"
    )
```

Also add `updated_at` to `ChangesetSummary`:

```python
# In class ChangesetSummary, after created_at:
class ChangesetSummary(BaseModel):
    id: str
    status: str
    created_at: str
    updated_at: str | None = None
    source_type: SourceType
    change_count: int
    routing: RoutingInfo | None
    feedback: str | None
    parent_changeset_id: str | None
```

- [ ] **Step 2: Add DB column migration for `updated_at`**

In `src/db/changesets.py`, add a migration method after `_maybe_add_source_type_column`:

```python
# Add after _maybe_add_source_type_column call in _create_table:
self._maybe_add_updated_at_column()
```

```python
# New method after _maybe_add_source_type_column:
# Add updated_at column to existing tables.
def _maybe_add_updated_at_column(self) -> None:
    cols = [
        row["name"]
        for row in self._conn.execute("PRAGMA table_info(changesets)").fetchall()
    ]
    if "updated_at" not in cols:
        self._conn.execute(
            "ALTER TABLE changesets ADD COLUMN updated_at TEXT"
        )
        self._conn.commit()
```

- [ ] **Step 3: Update `set()` to persist `updated_at`**

The `set()` method stores the full model as JSON in `data`, so `updated_at` is already included via `model_dump_json()`. No change needed to `set()`.

- [ ] **Step 4: Verify existing tests pass**

Run: `uv run pytest tests/unit/test_models.py tests/integration/test_store.py -v`
Expected: PASS (updated_at defaults to None, backward compatible)

- [ ] **Step 5: Commit**

```bash
git add src/models/changesets.py src/db/changesets.py
git commit -m "feat: add updated_at field to Changeset model + DB migration"
```

---

## Task 2: Backend — `merge_changes()` Method

**Files:**
- Modify: `src/db/changesets.py` (add method)
- Create: `tests/unit/test_changeset_store.py`

- [ ] **Step 1: Write failing tests for merge_changes**

Create `tests/unit/test_changeset_store.py`:

```python
import pytest
from datetime import datetime, timezone

from src.db.changesets import ChangesetStore
from src.models import Changeset, ProposedChange
from src.agent.diff import generate_diff


def make_change(path: str, original: str = "old", proposed: str = "new", **kw) -> ProposedChange:
    return ProposedChange(
        id=kw.get("id", f"ch-{path}"),
        tool_name=kw.get("tool_name", "replace_note"),
        input={"path": path, "content": proposed},
        original_content=original,
        proposed_content=proposed,
        diff=generate_diff(path, original, proposed),
        status=kw.get("status", "pending"),
    )


def make_changeset(changes: list[ProposedChange], **kw) -> Changeset:
    now = datetime.now(timezone.utc).isoformat()
    return Changeset(
        id=kw.get("id", "cs-1"),
        changes=changes,
        reasoning="test",
        source_type="clawdy",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def store():
    s = ChangesetStore(":memory:")
    yield s
    s.close()


class TestMergeChanges:
    def test_updates_existing_path(self, store):
        cs = make_changeset([make_change("a.md", "old", "v1")])
        store.set(cs)

        new_changes = [make_change("a.md", "old", "v2", id="new-ch-a")]
        result = store.merge_changes("cs-1", new_changes)

        assert result is not None
        assert len(result.changes) == 1
        assert result.changes[0].proposed_content == "v2"
        # ID preserved from original
        assert result.changes[0].id == "ch-a.md"
        # Status reset to pending
        assert result.changes[0].status == "pending"

    def test_adds_new_path(self, store):
        cs = make_changeset([make_change("a.md")])
        store.set(cs)

        new_changes = [make_change("a.md"), make_change("b.md")]
        result = store.merge_changes("cs-1", new_changes)

        assert result is not None
        assert len(result.changes) == 2
        paths = {c.input["path"] for c in result.changes}
        assert paths == {"a.md", "b.md"}

    def test_removes_path_not_in_new(self, store):
        cs = make_changeset([make_change("a.md"), make_change("b.md")])
        store.set(cs)

        new_changes = [make_change("a.md")]
        result = store.merge_changes("cs-1", new_changes)

        assert result is not None
        assert len(result.changes) == 1
        assert result.changes[0].input["path"] == "a.md"

    def test_deletes_changeset_when_zero_changes(self, store):
        cs = make_changeset([make_change("a.md")])
        store.set(cs)

        # New changes don't include a.md => removed => 0 changes
        result = store.merge_changes("cs-1", [])
        assert result is None
        assert store.get("cs-1") is None

    def test_resets_approved_status_on_update(self, store):
        change = make_change("a.md", status="approved")
        cs = make_changeset([change])
        store.set(cs)

        new_changes = [make_change("a.md", "old", "v2")]
        result = store.merge_changes("cs-1", new_changes)

        assert result is not None
        assert result.changes[0].status == "pending"

    def test_updates_updated_at(self, store):
        cs = make_changeset([make_change("a.md")])
        original_updated = cs.updated_at
        store.set(cs)

        new_changes = [make_change("a.md", "old", "v2")]
        result = store.merge_changes("cs-1", new_changes)

        assert result is not None
        assert result.updated_at is not None
        assert result.updated_at != original_updated

    def test_returns_none_for_missing_changeset(self, store):
        result = store.merge_changes("nonexistent", [make_change("a.md")])
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_changeset_store.py -v`
Expected: FAIL — `merge_changes` does not exist

- [ ] **Step 3: Implement `merge_changes()`**

Add to `src/db/changesets.py` after the `get_all_filtered` method:

```python
# Merge new changes into an existing changeset by file path.
#
# Matches by `change.input["path"]`:
# - Path exists in current: update content/diff, reset status to pending, keep ID.
# - Path is new: append as new ProposedChange.
# - Path in current but not in new: remove it.
# Deletes the changeset if zero changes remain after merge.
#
# Args:
#     changeset_id: ID of the changeset to merge into.
#     new_changes: List of ProposedChange with updated content.
#
# Returns:
#     Updated Changeset, or None if changeset was deleted or not found.
def merge_changes(
    self, changeset_id: str, new_changes: list[ProposedChange]
) -> Changeset | None:
    from datetime import datetime, timezone

    cs = self.get(changeset_id)
    if cs is None:
        return None

    new_by_path: dict[str, ProposedChange] = {}
    for nc in new_changes:
        path = nc.input.get("path", "")
        new_by_path[path] = nc

    existing_by_path: dict[str, ProposedChange] = {}
    for ec in cs.changes:
        path = ec.input.get("path", "")
        existing_by_path[path] = ec

    merged: list[ProposedChange] = []

    # Update existing or remove
    for path, existing in existing_by_path.items():
        if path in new_by_path:
            nc = new_by_path[path]
            merged.append(ProposedChange(
                id=existing.id,
                tool_name=nc.tool_name,
                input=nc.input,
                original_content=nc.original_content,
                proposed_content=nc.proposed_content,
                diff=nc.diff,
                status="pending",
            ))

    # Add new paths
    for path, nc in new_by_path.items():
        if path not in existing_by_path:
            merged.append(nc)

    if not merged:
        self.delete(changeset_id)
        return None

    cs.changes = merged
    cs.updated_at = datetime.now(timezone.utc).isoformat()
    self.set(cs)
    return cs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_changeset_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/changesets.py tests/unit/test_changeset_store.py
git commit -m "feat: add merge_changes() to ChangesetStore for changeset stacking"
```

---

## Task 3: Backend — Clawdy Poll Stacking

**Files:**
- Modify: `src/clawdy/service.py:282-368` (poll method)
- Modify: `tests/unit/test_clawdy_service.py` (update + add tests)

- [ ] **Step 1: Write failing test for stacking behavior**

Add to `tests/unit/test_clawdy_service.py` in `TestClawdyServicePoll`:

```python
def test_poll_merges_into_pending_changeset(self, tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    (main / "A.md").write_text("main A")

    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / "A.md").write_text("copy A")
    (copy / ".git").mkdir()  # Mark as git repo

    settings = SettingsStore(":memory:")
    settings.set("vault_path", str(main))
    settings.set("clawdy_copy_vault_path", str(copy))
    settings.set("clawdy_enabled", "true")

    store = ChangesetStore(":memory:")

    # Pre-existing pending changeset
    existing_cs = Changeset(
        id="existing-cs",
        changes=[ProposedChange(
            id="ch-1",
            tool_name="replace_note",
            input={"path": "B.md", "content": "old"},
            original_content="orig",
            proposed_content="old",
            diff="",
        )],
        reasoning="test",
        source_type="clawdy",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    store.set(existing_cs)

    svc = ClawdyService(settings, store)
    with (
        patch("src.clawdy.service.pull"),
        patch("src.clawdy.service.snapshot_vault", return_value={}),
        patch("src.clawdy.service.diff_vaults", return_value=(
            [("A.md", "main A", "copy A")], [], []
        )),
    ):
        svc.poll(str(main))

    # Should have merged, not skipped
    merged = store.get("existing-cs")
    assert merged is not None
    paths = {c.input["path"] for c in merged.changes}
    # B.md removed (not in new diffs), A.md added
    assert "A.md" in paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestClawdyServicePoll::test_poll_merges_into_pending_changeset -v`
Expected: FAIL (poll currently skips when pending exists)

- [ ] **Step 3: Modify `poll()` to stack instead of skip**

In `src/clawdy/service.py`, replace lines 292-298 (the skip-if-pending block) with merge logic:

```python
        # Check for pending clawdy changeset (for stacking)
        pending, count = self._changeset_store.get_all_filtered(
            status="pending", source_type="clawdy", limit=1
        )
        pending_cs = pending[0] if count > 0 else None
```

Then at the end of poll(), replace the changeset creation block (around lines 356-362) with:

```python
            cs = create_clawdy_changeset(main_vault, self.copy_vault_path, diffs=openclaw_diffs)
            if cs and pending_cs:
                # Merge into existing pending changeset
                merged = self._changeset_store.merge_changes(pending_cs.id, cs.changes)
                if merged:
                    tools = {}
                    for c in merged.changes:
                        tools[c.tool_name] = tools.get(c.tool_name, 0) + 1
                    logger.info(
                        "clawdy: merged into changeset %s, now %d changes (%s)",
                        merged.id, len(merged.changes), tools,
                    )
            elif cs:
                # Create new changeset
                tools = {}
                for c in cs.changes:
                    tools[c.tool_name] = tools.get(c.tool_name, 0) + 1
                logger.info(
                    "clawdy: created changeset %s with %d changes (%s)",
                    cs.id, len(cs.changes), tools,
                )
                self._changeset_store.set(cs)
            elif pending_cs:
                # No new changes but pending exists — merge empty to remove stale entries
                self._changeset_store.merge_changes(pending_cs.id, [])
```

- [ ] **Step 4: Update the existing skip test**

In `tests/unit/test_clawdy_service.py`, update `test_poll_skips_when_pending_changeset_exists` — it should now verify that poll continues (doesn't skip) and merges. Rename to `test_poll_merges_when_pending_changeset_exists` or remove if redundant with the new test.

- [ ] **Step 5: Run all clawdy tests**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat: clawdy poll stacking — merge into pending changeset instead of skipping"
```

---

## Task 4: Frontend — `updated_at` in Types

**Files:**
- Modify: `ui/src/types.ts:67-85` (Changeset)
- Modify: `ui/src/types.ts:160-169` (ChangesetSummary)

- [ ] **Step 1: Add `updated_at` to both interfaces**

In `ui/src/types.ts`, add after `created_at` in `Changeset`:

```typescript
  created_at: string;
  updated_at: string | null;
```

Add after `created_at` in `ChangesetSummary`:

```typescript
  created_at: string;
  updated_at: string | null;
```

- [ ] **Step 2: Run frontend tests to verify nothing breaks**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Update factory to include `updated_at`**

In `ui/src/__tests__/factories.ts`, add `updated_at: null` to `makeChangeset()` and `makeChangesetSummary()`.

- [ ] **Step 4: Commit**

```bash
git add ui/src/types.ts ui/src/__tests__/factories.ts
git commit -m "feat: add updated_at to Changeset and ChangesetSummary types"
```

---

## Task 5: Frontend — `useChangesetActions` Hook

**Files:**
- Create: `ui/src/hooks/useChangesetActions.ts`

This is extracted from `ChangesetReview.tsx` lines 34-200. The hook owns all changeset mutation state and API calls.

- [ ] **Step 1: Create the hook file**

Create `ui/src/hooks/useChangesetActions.ts`:

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import type { ProposedChange, SourceType } from "../types";
import {
  fetchChangeset,
  updateChangeStatus,
  updateChangeContent,
  applyChangeset,
  rejectChangeset,
  convergeClawdy,
  fetchClawdyConfig,
} from "../api/client";
import { formatError } from "../utils";

type ViewMode = "diff" | "preview" | "edit";

interface UseChangesetActionsInput {
  changesetId: string;
  initialChanges: ProposedChange[];
  sourceType: SourceType;
  onDone: () => void;
}

interface UseChangesetActionsReturn {
  changes: ProposedChange[];
  setChangeStatus: (changeId: string, status: "approved" | "rejected" | "pending") => void;
  setAllStatuses: (status: "approved" | "rejected") => void;
  toggleChange: (changeId: string) => void;
  handleApply: () => Promise<void>;
  handleReject: () => Promise<void>;
  handleEditChange: (changeId: string, content: string) => void;
  applying: boolean;
  statusError: string | null;
  result: { applied: string[]; failed: { id: string; error: string }[] } | null;
  savingIds: Set<string>;
  editBuffers: Record<string, string>;
  viewModes: Record<string, ViewMode>;
  setViewMode: (changeId: string, mode: ViewMode) => void;
}

export function useChangesetActions({
  changesetId,
  initialChanges,
  sourceType,
  onDone,
}: UseChangesetActionsInput): UseChangesetActionsReturn {
  const [changes, setChanges] = useState<ProposedChange[]>(initialChanges);
  const [viewModes, setViewModes] = useState<Record<string, ViewMode>>({});
  const [editBuffers, setEditBuffers] = useState<Record<string, string>>({});
  const [applying, setApplying] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    applied: string[];
    failed: { id: string; error: string }[];
  } | null>(null);

  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const debounceTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const syncedIds = useRef<Set<string>>(new Set());

  // Sync changes when initialChanges update (e.g., from stacking/merge)
  useEffect(() => {
    setChanges(initialChanges);
  }, [initialChanges]);

  const setChangeStatus = useCallback(
    (changeId: string, status: "approved" | "rejected" | "pending") => {
      setChanges((prev) =>
        prev.map((c) => (c.id === changeId ? { ...c, status } : c)),
      );
      syncedIds.current.delete(changeId);
    },
    [],
  );

  const toggleChange = useCallback(
    async (changeId: string) => {
      setChanges((prev) =>
        prev.map((c) => {
          if (c.id !== changeId) return c;
          const newStatus = c.status === "approved" ? "rejected" : "approved";
          updateChangeStatus(changesetId, changeId, newStatus).catch((err) =>
            setStatusError(formatError(err)),
          );
          return { ...c, status: newStatus };
        }),
      );
    },
    [changesetId],
  );

  const setAllStatuses = useCallback(
    (status: "approved" | "rejected") => {
      setChanges((prev) => prev.map((c) => ({ ...c, status })));
      syncedIds.current.clear();
    },
    [],
  );

  const handleEditChange = useCallback(
    (changeId: string, content: string) => {
      setEditBuffers((prev) => ({ ...prev, [changeId]: content }));
      setSavingIds((prev) => new Set(prev).add(changeId));

      if (debounceTimers.current[changeId]) {
        clearTimeout(debounceTimers.current[changeId]);
      }
      debounceTimers.current[changeId] = setTimeout(async () => {
        try {
          await updateChangeContent(changesetId, changeId, content);
          const cs = await fetchChangeset(changesetId);
          setChanges((prev) =>
            prev.map((c) => {
              const updated = cs.changes.find((uc) => uc.id === c.id);
              return updated ? { ...updated, status: c.status } : c;
            }),
          );
        } catch (err) {
          setStatusError(formatError(err));
        } finally {
          setSavingIds((prev) => {
            const next = new Set(prev);
            next.delete(changeId);
            return next;
          });
        }
      }, 500);
    },
    [changesetId],
  );

  // Converge to copy vault if one is configured, regardless of source type.
  const maybeConverge = useCallback(async () => {
    try {
      const config = await fetchClawdyConfig();
      if (config.copy_vault_path) {
        await convergeClawdy(changesetId);
      }
    } catch {
      // Convergence failure is non-fatal for non-clawdy sources
      if (sourceType === "clawdy") {
        throw new Error("Copy-vault sync failed");
      }
    }
  }, [changesetId, sourceType]);

  const handleApply = useCallback(async () => {
    const approvedIds = changes
      .filter((c) => c.status === "approved")
      .map((c) => c.id);

    if (approvedIds.length === 0) return;

    setApplying(true);
    try {
      const unsyncedChanges = changes.filter(
        (c) =>
          !syncedIds.current.has(c.id) &&
          (c.status === "approved" || c.status === "rejected"),
      );
      for (let i = 0; i < unsyncedChanges.length; i += 10) {
        const batch = unsyncedChanges.slice(i, i + 10);
        await Promise.all(
          batch.map((c) =>
            updateChangeStatus(
              changesetId,
              c.id,
              c.status as "approved" | "rejected",
            ),
          ),
        );
      }

      const res = await applyChangeset(changesetId, approvedIds);
      setResult(res);

      try {
        await maybeConverge();
      } catch (convergeErr) {
        setStatusError(
          `Applied to vault but copy-vault sync failed: ${formatError(convergeErr)}`,
        );
      }
    } catch (err) {
      setResult({
        applied: [],
        failed: [{ id: "all", error: String(err) }],
      });
    } finally {
      setApplying(false);
    }
  }, [changesetId, changes, maybeConverge]);

  const handleReject = useCallback(async () => {
    try {
      await rejectChangeset(changesetId);
      try {
        await maybeConverge();
      } catch {
        // Non-fatal for reject
      }
    } catch (err) {
      setStatusError(formatError(err));
      return;
    }
    onDone();
  }, [changesetId, onDone, maybeConverge]);

  const setViewMode = useCallback(
    (changeId: string, mode: ViewMode) => {
      setViewModes((prev) => ({ ...prev, [changeId]: mode }));
    },
    [],
  );

  return {
    changes,
    setChangeStatus,
    setAllStatuses,
    toggleChange,
    handleApply,
    handleReject,
    handleEditChange,
    applying,
    statusError,
    result,
    savingIds,
    editBuffers,
    viewModes,
    setViewMode,
  };
}
```

- [ ] **Step 2: Run frontend tests (should still pass, hook is unused)**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/src/hooks/useChangesetActions.ts
git commit -m "feat: extract useChangesetActions hook from ChangesetReview"
```

---

## Task 6: Frontend — `FileExplorer` Component

**Files:**
- Create: `ui/src/components/FileExplorer.tsx`
- Create: `ui/src/__tests__/components/FileExplorer.test.tsx`

- [ ] **Step 1: Write tests for FileExplorer**

Create `ui/src/__tests__/components/FileExplorer.test.tsx`:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FileExplorer } from "../../components/FileExplorer";
import { makeProposedChange } from "../factories";

describe("FileExplorer", () => {
  const changes = [
    makeProposedChange({
      id: "c1",
      tool_name: "replace_note",
      input: { path: "notes/papers/file1.md" },
      status: "pending",
    }),
    makeProposedChange({
      id: "c2",
      tool_name: "create_note",
      input: { path: "notes/papers/file2.md" },
      status: "approved",
    }),
    makeProposedChange({
      id: "c3",
      tool_name: "delete_note",
      input: { path: "notes/daily/log.md" },
      status: "rejected",
    }),
  ];

  it("renders folder tree structure", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(screen.getByText("notes")).toBeInTheDocument();
    expect(screen.getByText("papers")).toBeInTheDocument();
    expect(screen.getByText("daily")).toBeInTheDocument();
    expect(screen.getByText("file1.md")).toBeInTheDocument();
  });

  it("shows correct badges", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );
    expect(screen.getByText("MOD")).toBeInTheDocument();
    expect(screen.getByText("NEW")).toBeInTheDocument();
    expect(screen.getByText("DEL")).toBeInTheDocument();
  });

  it("calls onSelect when file clicked", () => {
    const onSelect = vi.fn();
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByText("file1.md"));
    expect(onSelect).toHaveBeenCalledWith("c1");
  });

  it("highlights selected file", () => {
    render(
      <FileExplorer changes={changes} selectedId="c1" onSelect={vi.fn()} />,
    );
    const row = screen.getByText("file1.md").closest("[data-testid='file-row-c1']");
    expect(row).toHaveClass("border-accent");
  });

  it("shows review count header", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );
    // 1 pending to review, 2 reviewed
    expect(screen.getByText(/1 to review/)).toBeInTheDocument();
    expect(screen.getByText(/2 reviewed/)).toBeInTheDocument();
  });

  it("collapses folder on click", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );
    // Click "papers" folder to collapse
    fireEvent.click(screen.getByText("papers"));
    // Files inside should be hidden
    expect(screen.queryByText("file1.md")).not.toBeInTheDocument();
  });

  it("shows check/cross icons for reviewed files", () => {
    render(
      <FileExplorer changes={changes} selectedId={null} onSelect={vi.fn()} />,
    );
    const approvedRow = screen.getByTestId("file-row-c2");
    expect(approvedRow.querySelector(".text-green")).toBeInTheDocument();
    const rejectedRow = screen.getByTestId("file-row-c3");
    expect(rejectedRow.querySelector(".text-red")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ui && bun run test -- FileExplorer`
Expected: FAIL — module not found

- [ ] **Step 3: Implement FileExplorer component**

Create `ui/src/components/FileExplorer.tsx`:

```tsx
import { useState, useMemo } from "react";
import type { ProposedChange } from "../types";

interface Props {
  changes: ProposedChange[];
  selectedId: string | null;
  onSelect: (changeId: string) => void;
}

interface TreeNode {
  name: string;
  children: Map<string, TreeNode>;
  change: ProposedChange | null;
}

function buildTree(changes: ProposedChange[]): TreeNode {
  const root: TreeNode = { name: "", children: new Map(), change: null };

  for (const change of changes) {
    const path = change.input.path as string;
    const parts = path.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          children: new Map(),
          change: i === parts.length - 1 ? change : null,
        });
      } else if (i === parts.length - 1) {
        current.children.get(part)!.change = change;
      }
      current = current.children.get(part)!;
    }
  }

  return root;
}

function getBadge(toolName: string): { label: string; className: string } {
  switch (toolName) {
    case "create_note":
      return { label: "NEW", className: "bg-green/10 text-green" };
    case "delete_note":
      return { label: "DEL", className: "bg-red/10 text-red" };
    default:
      return { label: "MOD", className: "bg-yellow/10 text-yellow" };
  }
}

function FolderNode({
  node,
  selectedId,
  onSelect,
  depth,
}: {
  node: TreeNode;
  selectedId: string | null;
  onSelect: (changeId: string) => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const children = Array.from(node.children.values());
  const folders = children.filter((c) => c.children.size > 0 || !c.change);
  const files = children.filter((c) => c.change !== null && c.children.size === 0);

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-1.5 py-1 px-2 text-xs text-muted hover:text-foreground hover:bg-elevated/50 bg-transparent border-none cursor-pointer text-left"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <span
          className={`text-[10px] transition-transform ${expanded ? "rotate-90" : ""}`}
        >
          &#9654;
        </span>
        <span className="font-medium">{node.name}</span>
      </button>
      {expanded && (
        <div>
          {folders.map((folder) => (
            <FolderNode
              key={folder.name}
              node={folder}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
          {files.map((file) => {
            const change = file.change!;
            const isSelected = selectedId === change.id;
            const isReviewed =
              change.status === "approved" || change.status === "rejected";
            const badge = getBadge(change.tool_name);

            return (
              <button
                key={change.id}
                data-testid={`file-row-${change.id}`}
                onClick={() => onSelect(change.id)}
                className={`w-full flex items-center gap-1.5 py-1 px-2 text-xs bg-transparent border-none cursor-pointer text-left border-l-2 transition-colors ${
                  isSelected
                    ? "border-accent bg-accent/5 text-foreground"
                    : "border-transparent hover:bg-elevated/50"
                } ${isReviewed ? "opacity-60" : ""}`}
                style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}
              >
                {isReviewed && (
                  <span
                    className={`text-[10px] flex-shrink-0 ${change.status === "approved" ? "text-green" : "text-red"}`}
                  >
                    {change.status === "approved" ? "\u2713" : "\u2717"}
                  </span>
                )}
                <span className="truncate">{file.name}</span>
                <span
                  className={`text-[9px] font-bold px-1 py-0 rounded flex-shrink-0 ml-auto ${badge.className}`}
                >
                  {badge.label}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function FileExplorer({ changes, selectedId, onSelect }: Props) {
  const tree = useMemo(() => buildTree(changes), [changes]);

  const pendingCount = changes.filter((c) => c.status === "pending").length;
  const reviewedCount = changes.filter(
    (c) => c.status === "approved" || c.status === "rejected",
  ).length;

  const topChildren = Array.from(tree.children.values());

  return (
    <div className="flex flex-col h-full border-r border-border" style={{ width: "250px", minWidth: "250px" }}>
      <div className="px-3 py-2 border-b border-border text-[10px] text-muted">
        <span className="font-medium">{pendingCount} to review</span>
        {reviewedCount > 0 && (
          <span className="ml-2">{reviewedCount} reviewed</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto py-1">
        {topChildren.map((node) =>
          node.change && node.children.size === 0 ? (
            // Top-level file (no folder)
            <button
              key={node.change.id}
              data-testid={`file-row-${node.change.id}`}
              onClick={() => onSelect(node.change!.id)}
              className={`w-full flex items-center gap-1.5 py-1 px-3 text-xs bg-transparent border-none cursor-pointer text-left border-l-2 transition-colors ${
                selectedId === node.change.id
                  ? "border-accent bg-accent/5 text-foreground"
                  : "border-transparent hover:bg-elevated/50"
              } ${node.change.status === "approved" || node.change.status === "rejected" ? "opacity-60" : ""}`}
            >
              {(node.change.status === "approved" || node.change.status === "rejected") && (
                <span
                  className={`text-[10px] flex-shrink-0 ${node.change.status === "approved" ? "text-green" : "text-red"}`}
                >
                  {node.change.status === "approved" ? "\u2713" : "\u2717"}
                </span>
              )}
              <span className="truncate">{node.name}</span>
              <span
                className={`text-[9px] font-bold px-1 py-0 rounded flex-shrink-0 ml-auto ${getBadge(node.change.tool_name).className}`}
              >
                {getBadge(node.change.tool_name).label}
              </span>
            </button>
          ) : (
            <FolderNode
              key={node.name}
              node={node}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={0}
            />
          ),
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd ui && bun run test -- FileExplorer`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/FileExplorer.tsx ui/src/__tests__/components/FileExplorer.test.tsx
git commit -m "feat: add FileExplorer component with folder tree and change badges"
```

---

## Task 7: Frontend — Simplify `ChangesetReview` to Single-Change

**Files:**
- Modify: `ui/src/components/ChangesetReview.tsx`
- Modify: `ui/src/__tests__/components/ChangesetReview.test.tsx`

The component now only handles single-change rendering. Multi-change is handled by ChangesetDetailPage's three-panel layout. It uses `useChangesetActions` internally.

- [ ] **Step 1: Rewrite ChangesetReview**

Replace `ui/src/components/ChangesetReview.tsx` entirely:

```tsx
import { useState, useEffect } from "react";
import type { ProposedChange, SourceType } from "../types";
import { fetchChangeset } from "../api/client";
import { useChangesetActions } from "../hooks/useChangesetActions";
import { DiffViewer } from "./DiffViewer";
import { MarkdownPreview } from "./MarkdownPreview";
import { Skeleton } from "./Skeleton";

type ViewMode = "diff" | "preview" | "edit";

interface Props {
  changesetId: string;
  initialChanges: ProposedChange[];
  onDone: () => void;
  readOnly?: boolean;
  sourceType?: SourceType;
}

export function ChangesetReview({
  changesetId,
  initialChanges,
  onDone,
  readOnly = false,
  sourceType = "web",
}: Props) {
  const [loadingChangeset, setLoadingChangeset] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [resolvedChanges, setResolvedChanges] = useState<ProposedChange[]>(initialChanges);

  // If no initial changes provided, fetch from server
  useEffect(() => {
    if (initialChanges.length === 0 && changesetId) {
      setLoadingChangeset(true);
      setFetchError(null);
      fetchChangeset(changesetId)
        .then((cs) => setResolvedChanges(cs.changes))
        .catch((err) => setFetchError(String(err)))
        .finally(() => setLoadingChangeset(false));
    }
  }, [changesetId, initialChanges]);

  const {
    changes,
    handleApply,
    handleReject,
    handleEditChange,
    applying,
    statusError,
    result,
    savingIds,
    editBuffers,
    viewModes,
    setViewMode,
  } = useChangesetActions({
    changesetId,
    initialChanges: resolvedChanges,
    sourceType,
    onDone,
  });

  if (loadingChangeset) {
    return (
      <div className="bg-surface border border-border rounded p-4 flex flex-col gap-3">
        <div className="flex gap-3">
          <Skeleton h="h-4" w="w-24" />
          <Skeleton h="h-4" w="w-32" />
        </div>
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} h="h-3" w={i % 2 === 0 ? "w-full" : "w-3/4"} />
        ))}
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-red mb-3">Failed to load changeset: {fetchError}</p>
        <button
          onClick={onDone}
          className="bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Back
        </button>
      </div>
    );
  }

  if (changes.length === 0) {
    return (
      <div className="bg-surface border border-border rounded p-5 text-center">
        <p className="text-muted mb-3">
          The agent completed without proposing any changes.
        </p>
        <button
          onClick={onDone}
          className="bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Done
        </button>
      </div>
    );
  }

  if (result) {
    const targetPaths = changes
      .filter((c) => result.applied.includes(c.id))
      .map((c) => c.input.path as string);

    return (
      <div className="bg-surface border border-border rounded p-5 flex flex-col items-center gap-3">
        {result.applied.length > 0 && (
          <>
            <svg width="32" height="32" viewBox="0 0 16 16" fill="currentColor" className="text-green">
              <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0m3.78 4.97a.75.75 0 0 0-1.06 0L7 8.69 5.28 6.97a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25a.75.75 0 0 0 0-1.06" />
            </svg>
            <h3 className="text-sm font-semibold m-0">
              {result.applied.length} change{result.applied.length !== 1 ? "s" : ""} written to vault
            </h3>
            {targetPaths.length > 0 && (
              <div className="flex flex-col gap-1">
                {targetPaths.map((p) => (
                  <span key={p} className="text-xs font-mono text-muted">{p}</span>
                ))}
              </div>
            )}
          </>
        )}
        {result.failed.length > 0 && (
          <div className="text-center">
            <p className="text-red text-sm">{result.failed.length} change(s) failed:</p>
            <ul className="text-xs text-red list-none p-0">
              {result.failed.map((f) => (
                <li key={f.id}>{f.error}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          onClick={onDone}
          className="mt-2 bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Start New
        </button>
      </div>
    );
  }

  // Single-change view only
  const change = changes[0];
  const mode = viewModes[change.id] ?? (change.tool_name === "create_note" ? "preview" : "diff");
  const filePath = change.input.path as string;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          Review Change
        </h3>
        <div className="flex border border-border rounded overflow-hidden">
          {change.tool_name !== "create_note" && (
            <button
              onClick={() => setViewMode(change.id, "diff")}
              className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "diff" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
            >
              Diff
            </button>
          )}
          <button
            onClick={() => setViewMode(change.id, "preview")}
            className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "preview" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
          >
            Preview
          </button>
          {!readOnly && (
            <button
              onClick={() => setViewMode(change.id, "edit")}
              className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "edit" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
            >
              Edit
            </button>
          )}
        </div>
      </div>

      {statusError && (
        <p className="text-red text-xs mb-2">Failed to update status: {statusError}</p>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto">
        {mode === "diff" && change.tool_name !== "create_note" ? (
          <DiffViewer
            diff={change.diff}
            filePath={filePath}
            isNew={false}
            originalContent={change.original_content}
            proposedContent={change.proposed_content}
          />
        ) : mode === "edit" && !readOnly ? (
          <textarea
            className="w-full flex-1 min-h-64 bg-bg border border-border rounded p-3 text-sm text-foreground font-mono resize-y outline-none focus:border-accent"
            value={editBuffers[change.id] ?? change.proposed_content}
            onChange={(e) => handleEditChange(change.id, e.target.value)}
          />
        ) : (
          <MarkdownPreview content={change.proposed_content} />
        )}
        {mode === "edit" && savingIds.has(change.id) && (
          <span className="text-[10px] text-muted animate-pulse mt-1">Saving...</span>
        )}
      </div>

      {!readOnly && (
        <div className="flex gap-3 pt-4 border-t border-border">
          <button
            onClick={handleApply}
            disabled={applying}
            className="bg-accent text-crust border-none py-2 px-5 rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {applying ? "Applying..." : "Approve"}
          </button>
          <button
            onClick={handleReject}
            className="bg-transparent text-red border border-red/30 py-2 px-5 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover:bg-red/5"
            disabled={applying}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
```

**Important difference from original:** The single-change `handleApply` auto-approves the change before applying. Add this to the hook's `handleApply`:
The existing hook already handles this — when there's one change, the user clicks "Approve" which calls `handleApply`. The hook needs the change to be approved first. For single-change, we should auto-approve in the button handler. Wrap the onClick:

```tsx
onClick={async () => {
  // Auto-approve the single change before applying
  await updateChangeStatus(changesetId, change.id, "approved");
  handleApply();
}}
```

Actually, simpler: modify the button to call `setChangeStatus` then `handleApply`:

```tsx
onClick={() => {
  setChangeStatus(change.id, "approved");
  // Small delay to let state settle, then apply
  setTimeout(() => handleApply(), 0);
}}
```

Wait — the original code for single change had `approvedCount === 0` disable. The simpler approach: the single-change Approve button should call a dedicated function that approves + applies. Add to the hook or handle inline. Let's handle it inline in ChangesetReview since it's single-change specific behavior.

- [ ] **Step 2: Update ChangesetReview tests**

Update `ui/src/__tests__/components/ChangesetReview.test.tsx` — the tests check for tab visibility which still applies:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ChangesetReview } from "../../components/ChangesetReview";
import { makeProposedChange } from "../factories";

describe("ChangesetReview", () => {
  const baseProps = {
    changesetId: "cs-1",
    onDone: vi.fn(),
  };

  it("hides Diff tab for create_note changes", () => {
    render(
      <ChangesetReview
        {...baseProps}
        initialChanges={[makeProposedChange({ tool_name: "create_note" })]}
      />,
    );
    expect(screen.queryByRole("button", { name: "Diff" })).toBeNull();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
  });

  it("shows Diff tab for update_note changes", () => {
    render(
      <ChangesetReview
        {...baseProps}
        initialChanges={[
          makeProposedChange({
            tool_name: "update_note",
            original_content: "original",
          }),
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "Diff" })).toBeInTheDocument();
  });

  it("defaults create_note to preview mode", () => {
    render(
      <ChangesetReview
        {...baseProps}
        initialChanges={[
          makeProposedChange({
            tool_name: "create_note",
            proposed_content: "# Hello World",
          }),
        ]}
      />,
    );
    expect(screen.getByText("Hello World")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests**

Run: `cd ui && bun run test -- ChangesetReview`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/ChangesetReview.tsx ui/src/__tests__/components/ChangesetReview.test.tsx
git commit -m "refactor: simplify ChangesetReview to single-change, use useChangesetActions hook"
```

---

## Task 8: Frontend — `ChangesetDetailPage` Three-Panel Layout

**Files:**
- Modify: `ui/src/pages/ChangesetDetailPage.tsx`

This is the largest frontend task. The page switches layout based on `changes.length`:
- **Single change (<=1):** Current layout with simplified ChangesetReview
- **Multi-change (>1):** Three-panel: FileExplorer (left, 250px) + viewer (right) + bottom action bar

- [ ] **Step 1: Rewrite ChangesetDetailPage**

Replace the content area (the `<div ref={containerRef}>` section) with conditional layout. The full rewrite of `ChangesetDetailPage.tsx`:

```tsx
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router";
import type { Changeset, TokenUsage, PassageAnnotation } from "../types";
import {
  fetchChangeset,
  fetchChangesetCost,
  requestChanges,
  regenerateChangeset,
  deleteChangeset,
  convergeClawdy,
} from "../api/client";
import { formatError, formatTokens } from "../utils";
import { ErrorAlert } from "../components/ErrorAlert";
import { ChangesetReview } from "../components/ChangesetReview";
import { FileExplorer } from "../components/FileExplorer";
import { useChangesetActions } from "../hooks/useChangesetActions";
import { DiffViewer } from "../components/DiffViewer";
import { MarkdownPreview } from "../components/MarkdownPreview";
import {
  AnnotationFeedback,
  formatAnnotations,
} from "../components/AnnotationFeedback";
import { StatusBadge } from "../components/StatusBadge";
import { Skeleton } from "../components/Skeleton";
import { useClickOutside } from "../hooks/useClickOutside";

function DeleteConfirmPopover({
  onConfirm,
  onCancel,
}: {
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, onCancel);

  return (
    <div
      ref={ref}
      data-testid="delete-confirm-popover"
      className="absolute right-0 top-full mt-1 z-10 bg-surface border border-border rounded p-3 shadow-lg min-w-[200px]"
    >
      <p className="text-xs text-muted m-0 mb-2">
        Permanently delete this changeset?
      </p>
      <div className="flex gap-2 justify-end">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onCancel();
          }}
          className="text-xs px-3 py-1 rounded bg-transparent border border-border text-muted cursor-pointer hover:text-foreground"
        >
          Cancel
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onConfirm();
          }}
          data-testid="confirm-delete-btn"
          className="text-xs px-3 py-1 rounded bg-red/15 border border-red/30 text-red cursor-pointer hover:bg-red/25"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function CostDisplay({ usage }: { usage: TokenUsage }) {
  return (
    <div className="flex flex-col gap-1 text-xs">
      <div className="flex justify-between gap-4">
        <span className="text-muted">Cost</span>
        <span className="font-medium">${usage.total_cost_usd.toFixed(4)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-muted">Tokens</span>
        <span>
          {formatTokens(usage.input_tokens)} in &middot;{" "}
          {formatTokens(usage.output_tokens)} out
        </span>
      </div>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="bg-surface border border-border rounded p-3 flex gap-3">
        <Skeleton h="h-4" w="w-16" className="rounded-full" />
        <Skeleton h="h-3" w="w-32" />
        <Skeleton h="h-3" w="w-24" className="ml-auto" />
      </div>
      <div className="bg-surface border border-border rounded p-4 flex flex-col gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <Skeleton key={i} h="h-3" w={i % 3 === 0 ? "w-full" : "w-4/5"} />
        ))}
      </div>
    </div>
  );
}

// Multi-change viewer: FileExplorer + diff viewer + bottom actions
function MultiChangeViewer({
  detail,
  onDone,
}: {
  detail: Changeset;
  onDone: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(
    detail.changes[0]?.id ?? null,
  );

  const isInteractive =
    detail.status === "pending" || detail.status === "partially_applied";

  const {
    changes,
    setChangeStatus,
    setAllStatuses,
    handleApply,
    handleReject,
    handleEditChange,
    applying,
    statusError,
    result,
    savingIds,
    editBuffers,
    viewModes,
    setViewMode,
  } = useChangesetActions({
    changesetId: detail.id,
    initialChanges: detail.changes,
    sourceType: detail.source_type,
    onDone,
  });

  const selectedChange = changes.find((c) => c.id === selectedId) ?? changes[0];
  const mode =
    viewModes[selectedChange?.id] ??
    (selectedChange?.tool_name === "create_note" ? "preview" : "diff");
  const filePath = (selectedChange?.input?.path as string) ?? "";
  const approvedCount = changes.filter((c) => c.status === "approved").length;

  const toolLabel =
    selectedChange?.tool_name === "create_note"
      ? "NEW"
      : selectedChange?.tool_name === "delete_note"
        ? "DEL"
        : "MOD";
  const toolBadgeClass =
    selectedChange?.tool_name === "create_note"
      ? "bg-green/10 text-green"
      : selectedChange?.tool_name === "delete_note"
        ? "bg-red/10 text-red"
        : "bg-yellow/10 text-yellow";

  if (result) {
    const targetPaths = changes
      .filter((c) => result.applied.includes(c.id))
      .map((c) => c.input.path as string);

    return (
      <div className="bg-surface border border-border rounded p-5 flex flex-col items-center gap-3">
        {result.applied.length > 0 && (
          <>
            <svg width="32" height="32" viewBox="0 0 16 16" fill="currentColor" className="text-green">
              <path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0m3.78 4.97a.75.75 0 0 0-1.06 0L7 8.69 5.28 6.97a.75.75 0 0 0-1.06 1.06l2.25 2.25a.75.75 0 0 0 1.06 0l4.25-4.25a.75.75 0 0 0 0-1.06" />
            </svg>
            <h3 className="text-sm font-semibold m-0">
              {result.applied.length} change{result.applied.length !== 1 ? "s" : ""} written to vault
            </h3>
            {targetPaths.length > 0 && (
              <div className="flex flex-col gap-1">
                {targetPaths.map((p) => (
                  <span key={p} className="text-xs font-mono text-muted">{p}</span>
                ))}
              </div>
            )}
          </>
        )}
        {result.failed.length > 0 && (
          <div className="text-center">
            <p className="text-red text-sm">{result.failed.length} change(s) failed:</p>
            <ul className="text-xs text-red list-none p-0">
              {result.failed.map((f) => (
                <li key={f.id}>{f.error}</li>
              ))}
            </ul>
          </div>
        )}
        <button
          onClick={onDone}
          className="mt-2 bg-accent text-crust border-none py-2 px-5 rounded text-sm"
        >
          Done
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {statusError && (
        <p className="text-red text-xs mb-2">Failed to update: {statusError}</p>
      )}

      <div className="flex flex-1 min-h-0">
        {/* Left: FileExplorer */}
        <FileExplorer
          changes={changes}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />

        {/* Right: Viewer */}
        {selectedChange && (
          <div className="flex-1 flex flex-col min-w-0 min-h-0">
            {/* Viewer header */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-border">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-mono truncate">{filePath}</span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 ${toolBadgeClass}`}>
                  {toolLabel}
                </span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* View mode toggle */}
                <div className="flex border border-border rounded overflow-hidden">
                  {selectedChange.tool_name !== "create_note" && (
                    <button
                      onClick={() => setViewMode(selectedChange.id, "diff")}
                      className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "diff" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                    >
                      Diff
                    </button>
                  )}
                  <button
                    onClick={() => setViewMode(selectedChange.id, "preview")}
                    className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "preview" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                  >
                    Preview
                  </button>
                  {isInteractive && (
                    <button
                      onClick={() => setViewMode(selectedChange.id, "edit")}
                      className={`text-[11px] py-0.5 px-2.5 border-none cursor-pointer ${mode === "edit" ? "bg-accent text-crust" : "bg-elevated text-muted"}`}
                    >
                      Edit
                    </button>
                  )}
                </div>
                {/* Per-file approve/reject */}
                {isInteractive && selectedChange.status === "pending" && (
                  <>
                    <button
                      onClick={() => setChangeStatus(selectedChange.id, "approved")}
                      className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted hover:bg-green/10 hover:text-green"
                    >
                      &#10003; Approve
                    </button>
                    <button
                      onClick={() => setChangeStatus(selectedChange.id, "rejected")}
                      className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted/60 hover:bg-red/10 hover:text-red"
                    >
                      &#10005; Reject
                    </button>
                  </>
                )}
                {isInteractive &&
                  (selectedChange.status === "approved" || selectedChange.status === "rejected") && (
                    <button
                      onClick={() => setChangeStatus(selectedChange.id, "pending")}
                      className="py-0.5 px-2 rounded flex items-center gap-1 border-none cursor-pointer transition-colors text-[10px] font-bold bg-transparent text-muted hover:bg-accent/10 hover:text-accent"
                    >
                      &#8634; Undo
                    </button>
                  )}
              </div>
            </div>

            {/* Viewer content */}
            <div className="flex-1 min-h-0 overflow-y-auto p-4">
              {mode === "diff" && selectedChange.tool_name !== "create_note" ? (
                <DiffViewer
                  diff={selectedChange.diff}
                  filePath={filePath}
                  isNew={false}
                  originalContent={selectedChange.original_content}
                  proposedContent={selectedChange.proposed_content}
                />
              ) : mode === "edit" && isInteractive ? (
                <>
                  <textarea
                    className="w-full flex-1 min-h-64 bg-bg border border-border rounded p-3 text-sm text-foreground font-mono resize-y outline-none focus:border-accent"
                    value={editBuffers[selectedChange.id] ?? selectedChange.proposed_content}
                    onChange={(e) => handleEditChange(selectedChange.id, e.target.value)}
                  />
                  {savingIds.has(selectedChange.id) && (
                    <span className="text-[10px] text-muted animate-pulse mt-1">Saving...</span>
                  )}
                </>
              ) : (
                <MarkdownPreview content={selectedChange.proposed_content} />
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom: Collapsible actions */}
      {isInteractive && (
        <BottomActions
          approvedCount={approvedCount}
          applying={applying}
          onApply={handleApply}
          onReject={handleReject}
          onApproveAll={() => setAllStatuses("approved")}
          onRejectAll={() => setAllStatuses("rejected")}
        />
      )}
    </div>
  );
}

function BottomActions({
  approvedCount,
  applying,
  onApply,
  onReject,
  onApproveAll,
  onRejectAll,
}: {
  approvedCount: number;
  applying: boolean;
  onApply: () => void;
  onReject: () => void;
  onApproveAll: () => void;
  onRejectAll: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-t border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2 bg-transparent border-none cursor-pointer text-xs text-muted hover:text-foreground"
      >
        <span>Feedback & Actions</span>
        <span className={`transition-transform ${expanded ? "rotate-180" : ""}`}>&#9662;</span>
      </button>
      {expanded && (
        <div className="px-4 pb-3 flex flex-col gap-3">
          <div className="flex items-center gap-3 text-xs">
            <button
              onClick={onApproveAll}
              className="bg-transparent border-none text-green font-semibold flex items-center gap-1 cursor-pointer hover:brightness-125"
            >
              <span className="text-sm">&#10003;</span> Approve All
            </button>
            <span className="text-border">|</span>
            <button
              onClick={onRejectAll}
              className="bg-transparent border-none text-red font-semibold flex items-center gap-1 cursor-pointer hover:brightness-125"
            >
              <span className="text-sm">&#10005;</span> Reject All
            </button>
          </div>
          <div className="flex gap-3">
            <button
              onClick={onApply}
              disabled={applying || approvedCount === 0}
              className="bg-accent text-crust border-none py-2 px-5 rounded-lg text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {applying
                ? "Applying..."
                : `Apply ${approvedCount} Change${approvedCount !== 1 ? "s" : ""}`}
            </button>
            <button
              onClick={onReject}
              className="bg-transparent text-red border border-red/30 py-2 px-5 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover:bg-red/5"
              disabled={applying}
            >
              Reject All
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ChangesetDetailPage() {
  const { changesetId } = useParams<{ changesetId: string }>();
  const navigate = useNavigate();

  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<Changeset | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [usage, setUsage] = useState<TokenUsage | null>(null);
  const [annotations, setAnnotations] = useState<PassageAnnotation[]>([]);
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [converging, setConverging] = useState(false);

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setError(null);
    setAnnotations([]);
    setUsage(null);
    try {
      const [cs, cost] = await Promise.all([
        fetchChangeset(id),
        fetchChangesetCost(id),
      ]);
      setDetail(cs);
      setUsage(cost);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (changesetId) loadDetail(changesetId);
  }, [changesetId, loadDetail]);

  function backToList() {
    if (detailLoading) return;
    if (detail?.source_type === "clawdy") {
      navigate("/clawdy");
    } else {
      navigate("/changesets");
    }
  }

  const handleConverge = useCallback(async () => {
    if (!changesetId) return;
    setConverging(true);
    setError(null);
    try {
      await convergeClawdy(changesetId);
      const cs = await fetchChangeset(changesetId);
      setDetail(cs);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setConverging(false);
    }
  }, [changesetId]);

  const handleRequestChanges = useCallback(async () => {
    if (!changesetId || annotations.length === 0) return;
    setSubmittingFeedback(true);
    setError(null);
    try {
      await requestChanges(changesetId, formatAnnotations(annotations));
      const cs = await fetchChangeset(changesetId);
      setDetail(cs);
      setAnnotations([]);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setSubmittingFeedback(false);
    }
  }, [changesetId, annotations]);

  const handleRegenerate = useCallback(async () => {
    if (!changesetId) return;
    setRegenerating(true);
    setError(null);
    try {
      const newCs = await regenerateChangeset(changesetId);
      navigate(`/changesets/${newCs.id}`);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setRegenerating(false);
    }
  }, [changesetId, navigate]);

  const handleDelete = useCallback(async () => {
    if (!changesetId) return;
    setConfirmDelete(false);
    setDeleting(true);
    setError(null);
    try {
      await deleteChangeset(changesetId);
      backToList();
    } catch (err) {
      setError(formatError(err));
    } finally {
      setDeleting(false);
    }
  }, [changesetId]);

  const isInteractive =
    detail?.status === "pending" || detail?.status === "partially_applied";
  const showRegenerate = detail?.status === "revision_requested";
  const isClawdy = detail?.source_type === "clawdy";
  const allResolved = detail?.changes.every(
    (c) => c.status === "applied" || c.status === "rejected",
  );
  const showConverge =
    isClawdy &&
    allResolved &&
    detail?.status !== "applied" &&
    detail?.status !== "rejected";
  const isMultiChange = (detail?.changes.length ?? 0) > 1;

  // Show updated_at when it differs from created_at
  const showUpdatedAt =
    detail?.updated_at && detail.updated_at !== detail.created_at;

  return (
    <div className="flex flex-col gap-4 flex-1 min-h-0 py-6 px-8">
      <div className="flex items-center gap-3">
        <button
          onClick={backToList}
          className="text-muted hover:text-foreground bg-transparent border-none cursor-pointer text-lg p-0 leading-none"
          aria-label="Back to list"
          title="Back to list"
        >
          &larr;
        </button>
        <h2 className="text-base font-semibold m-0">Changeset Detail</h2>
      </div>

      {error && <ErrorAlert message={error} />}

      {detailLoading ? (
        <DetailSkeleton />
      ) : detail ? (
        <div className="flex flex-col gap-4 flex-1 min-h-0">
          {/* Top bar */}
          <div className="bg-surface border border-border rounded p-3 flex flex-wrap items-center gap-3 text-sm">
            <StatusBadge status={detail.status} />
            <span className="text-xs text-muted">
              {new Date(detail.created_at).toLocaleString()}
              {showUpdatedAt && (
                <span className="ml-1">
                  (updated {new Date(detail.updated_at!).toLocaleString()})
                </span>
              )}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface border border-border text-muted">
              {detail.source_type}
            </span>
            {detail.routing && (
              <span className="text-xs">
                <span className="text-muted">Route:</span>{" "}
                <span className="font-medium capitalize">
                  {detail.routing.action}
                </span>
                {detail.routing.target_path && (
                  <span className="font-mono text-xs ml-1">
                    &rarr; {detail.routing.target_path}
                  </span>
                )}
              </span>
            )}
            {usage && (
              <div className="ml-auto">
                <CostDisplay usage={usage} />
              </div>
            )}
            {showConverge && (
              <button
                onClick={handleConverge}
                disabled={converging}
                className="text-xs bg-green/15 text-green border border-green/30 rounded px-3 py-1 cursor-pointer hover:bg-green/25 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {converging ? "Syncing..." : "Finalize & Sync"}
              </button>
            )}
            <div className="relative">
              <button
                onClick={() => setConfirmDelete(true)}
                disabled={deleting}
                className="text-xs text-red bg-transparent border border-red/30 rounded px-3 py-1 cursor-pointer hover:bg-red/10 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="detail-delete"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
              {confirmDelete && (
                <DeleteConfirmPopover
                  onConfirm={handleDelete}
                  onCancel={() => setConfirmDelete(false)}
                />
              )}
            </div>
          </div>

          {detail.parent_changeset_id && (
            <div className="text-xs text-muted">
              Regenerated from{" "}
              <button
                onClick={() =>
                  navigate(`/changesets/${detail.parent_changeset_id}`)
                }
                className="text-accent underline bg-transparent border-none cursor-pointer p-0 text-xs"
              >
                Previous version
              </button>
            </div>
          )}

          {detail.feedback && detail.status === "revision_requested" && (
            <div className="bg-surface border border-border rounded p-3">
              <span className="text-xs text-muted block mb-1">Feedback:</span>
              <p className="text-sm m-0">{detail.feedback}</p>
            </div>
          )}

          {/* Content area — layout depends on change count */}
          {isMultiChange ? (
            <MultiChangeViewer detail={detail} onDone={backToList} />
          ) : (
            <SingleChangeLayout
              detail={detail}
              isInteractive={isInteractive ?? false}
              showRegenerate={showRegenerate ?? false}
              onDone={backToList}
              annotations={annotations}
              setAnnotations={setAnnotations}
              handleRequestChanges={handleRequestChanges}
              submittingFeedback={submittingFeedback}
              handleRegenerate={handleRegenerate}
              regenerating={regenerating}
            />
          )}
        </div>
      ) : (
        <div className="text-muted text-sm">Changeset not found.</div>
      )}
    </div>
  );
}

// Preserved original single-change layout with split pane
function SingleChangeLayout({
  detail,
  isInteractive,
  showRegenerate,
  onDone,
  annotations,
  setAnnotations,
  handleRequestChanges,
  submittingFeedback,
  handleRegenerate,
  regenerating,
}: {
  detail: Changeset;
  isInteractive: boolean;
  showRegenerate: boolean;
  onDone: () => void;
  annotations: PassageAnnotation[];
  setAnnotations: React.Dispatch<React.SetStateAction<PassageAnnotation[]>>;
  handleRequestChanges: () => Promise<void>;
  submittingFeedback: boolean;
  handleRegenerate: () => Promise<void>;
  regenerating: boolean;
}) {
  const [splitPercent, setSplitPercent] = useState(72);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(85, Math.max(40, pct)));
    };

    const onUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  return (
    <div ref={containerRef} className="flex flex-1 min-h-0 w-full">
      <div
        className="flex flex-col gap-4 min-w-0 min-h-0"
        style={{ width: isInteractive ? `${splitPercent}%` : "100%" }}
      >
        <ChangesetReview
          changesetId={detail.id}
          initialChanges={detail.changes}
          onDone={onDone}
          readOnly={!isInteractive}
          sourceType={detail.source_type}
        />

        {showRegenerate && (
          <div className="bg-surface border border-border rounded p-4 flex flex-col gap-3">
            <h4 className="text-sm font-medium m-0">Regenerate</h4>
            <p className="text-xs text-muted m-0">
              Re-run the agent with the feedback above to produce a new changeset.
            </p>
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className="self-start bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {regenerating ? "Regenerating..." : "Regenerate"}
            </button>
          </div>
        )}
      </div>

      {isInteractive && (
        <>
          <div
            onMouseDown={onDragStart}
            className="w-2 mx-3 self-stretch cursor-col-resize rounded-full bg-border hover:bg-accent transition-colors flex-shrink-0 relative flex flex-col items-center justify-center gap-0.5"
          >
            <span className="block w-1 h-1 rounded-full bg-muted/50" />
            <span className="block w-1 h-1 rounded-full bg-muted/50" />
            <span className="block w-1 h-1 rounded-full bg-muted/50" />
          </div>
          <div
            className="min-w-0 overflow-y-auto flex-shrink-0 pl-2"
            style={{ width: `${100 - splitPercent}%` }}
          >
            <AnnotationFeedback
              annotations={annotations}
              onAdd={(a) => setAnnotations((prev) => [...prev, a])}
              onRemove={(id) =>
                setAnnotations((prev) => prev.filter((a) => a.id !== id))
              }
              onSubmit={handleRequestChanges}
              submitting={submittingFeedback}
            />
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Run all frontend tests**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/ChangesetDetailPage.tsx
git commit -m "feat: three-panel layout for multi-change changesets with FileExplorer"
```

---

## Task 9: Backend — Convergence Generalization

**Files:**
- Modify: `src/server.py:1486-1533` (converge endpoint)
- Modify: `src/clawdy/service.py` (add `sync_applied_to_copy` function)

The converge endpoint currently rejects non-clawdy changesets. We need to generalize it so any changeset can sync applied changes to the copy vault.

- [ ] **Step 1: Add `sync_applied_to_copy` function**

In `src/clawdy/service.py`, add after `sync_main_to_copy`:

```python
# Copy applied changeset files from main vault to copy vault.
#
# For each applied change, reads the current file from main vault
# and writes it to copy vault so they stay in sync.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#     changes_map: Dict of {relative_path: {"tool_name": str, "status": str}}.
#
# Returns:
#     Number of files synced.
def sync_applied_to_copy(
    main_vault: str,
    copy_vault: str,
    changes_map: dict[str, dict[str, str]],
) -> int:
    count = 0
    for rel_path, info in changes_map.items():
        if info["status"] != "applied":
            continue

        main_file = Path(main_vault, rel_path)
        copy_file = Path(copy_vault, rel_path)

        if info["tool_name"] == "delete_note":
            if copy_file.exists():
                copy_file.unlink()
                count += 1
        elif main_file.exists():
            copy_file.parent.mkdir(parents=True, exist_ok=True)
            copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")
            count += 1

    return count
```

- [ ] **Step 2: Generalize the converge endpoint**

In `src/server.py`, modify the `converge_clawdy` route (line 1488):

Replace the `source_type != "clawdy"` check with logic that handles both clawdy and non-clawdy:

```python
# Run convergence — sync changeset results to copy vault.
@app.post("/clawdy/converge/{changeset_id}", tags=["Clawdy"])
async def converge_clawdy(changeset_id: str, request: Request):
    _require_vault(request)
    cs = _get_changeset_or_404(changeset_id)

    # Check all changes are in terminal state
    for change in cs.changes:
        if change.status not in ("applied", "rejected"):
            raise HTTPException(400, f"Change {change.id} is still {change.status}")

    config = _get_config(request)
    if not clawdy_service or not clawdy_service.copy_vault_path:
        raise HTTPException(400, "Clawdy not configured")

    changes_map = {}
    for change in cs.changes:
        path = change.input.get("path", "")
        changes_map[path] = {"tool_name": change.tool_name, "status": change.status}

    if cs.source_type == "clawdy":
        # Full convergence: handle both applied and rejected changes
        await asyncio.to_thread(
            converge_vaults, config.vault_path, clawdy_service.copy_vault_path, changes_map
        )
    else:
        # Non-clawdy: just copy applied changes to keep copy vault in sync
        await asyncio.to_thread(
            sync_applied_to_copy, config.vault_path, clawdy_service.copy_vault_path, changes_map
        )

    # ... rest of function unchanged (commit, push, update status)
```

Don't forget to import `sync_applied_to_copy` in `src/server.py`.

- [ ] **Step 3: Add test for sync_applied_to_copy**

Add to `tests/unit/test_clawdy_service.py`:

```python
class TestSyncAppliedToCopy:
    def test_copies_applied_replace_to_copy(self, tmp_path):
        main = tmp_path / "main"
        main.mkdir()
        (main / "A.md").write_text("updated content")
        copy = tmp_path / "copy"
        copy.mkdir()
        (copy / "A.md").write_text("old content")

        changes_map = {"A.md": {"tool_name": "replace_note", "status": "applied"}}
        count = sync_applied_to_copy(str(main), str(copy), changes_map)

        assert count == 1
        assert (copy / "A.md").read_text() == "updated content"

    def test_copies_applied_create_to_copy(self, tmp_path):
        main = tmp_path / "main"
        main.mkdir()
        (main / "new.md").write_text("new file")
        copy = tmp_path / "copy"
        copy.mkdir()

        changes_map = {"new.md": {"tool_name": "create_note", "status": "applied"}}
        count = sync_applied_to_copy(str(main), str(copy), changes_map)

        assert count == 1
        assert (copy / "new.md").read_text() == "new file"

    def test_deletes_applied_delete_from_copy(self, tmp_path):
        main = tmp_path / "main"
        main.mkdir()
        copy = tmp_path / "copy"
        copy.mkdir()
        (copy / "gone.md").write_text("to delete")

        changes_map = {"gone.md": {"tool_name": "delete_note", "status": "applied"}}
        count = sync_applied_to_copy(str(main), str(copy), changes_map)

        assert count == 1
        assert not (copy / "gone.md").exists()

    def test_skips_rejected_changes(self, tmp_path):
        main = tmp_path / "main"
        main.mkdir()
        (main / "A.md").write_text("main")
        copy = tmp_path / "copy"
        copy.mkdir()
        (copy / "A.md").write_text("copy")

        changes_map = {"A.md": {"tool_name": "replace_note", "status": "rejected"}}
        count = sync_applied_to_copy(str(main), str(copy), changes_map)

        assert count == 0
        assert (copy / "A.md").read_text() == "copy"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py src/server.py tests/unit/test_clawdy_service.py
git commit -m "feat: generalize convergence — sync applied changes to copy vault for all source types"
```

---

## Task 10: Final — Run Full Test Suite

- [ ] **Step 1: Run backend tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 2: Run frontend tests**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Build UI (for E2E readiness)**

Run: `cd ui && bun run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Final commit if any fixes needed**

---

## Unresolved Questions

1. Partition diff: current code seems correct per spec description — all diffs go to either changeset or auto-sync. The stacking change (Task 3) fixes the "skipped polls" issue. Is there a separate partition_diff bug beyond what stacking solves?
2. `updated_at` display in ChangesetSummary list views (ChangesetsPage, ClawdyInboxPage) — spec doesn't mention it. Skip for now?
3. AnnotationFeedback panel for multi-change layout — spec shows it in the bottom collapsible. Current impl puts bulk actions there. Should annotation feedback also move to the bottom panel for multi-change?
4. converge endpoint URL — keeping `/clawdy/converge/{id}` even for non-clawdy sources is a bit of a misnomer. Rename to `/changesets/{id}/converge`?
