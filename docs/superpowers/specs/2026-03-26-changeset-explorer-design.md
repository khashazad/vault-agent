# Changeset File Explorer & Clawdy Stacking

**Date**: 2026-03-26
**Scope**: Backend bug fixes (clawdy poll), new UI layout for multi-change changeset review, convergence generalization

---

## Problem

1. **Missing changes in Clawdy changesets**: `partition_diff()` filters diffs to only files changed during `git pull`. Files that differ between vaults but weren't in the pull get misclassified and silently auto-synced or ignored.
2. **Skipped polls**: When a pending clawdy changeset exists, `ClawdyService.poll()` skips entirely. New commits pushed to the copy vault are invisible until the user resolves the existing changeset.
3. **Flat change list**: The current accordion-based `ChangesetReview` doesn't show folder hierarchy. Navigating many changes is clunky compared to a VS Code-style file explorer.
4. **Clawdy-only convergence**: Only clawdy changesets sync back to the copy vault on apply/reject. Any changeset that modifies the main vault should propagate to the copy vault if one is configured.

## Design

### 1. Clawdy Poll — Changeset Stacking

**Current**: Poll skips if a pending clawdy changeset exists (line 293-298 in `service.py`).

**New**: Poll always runs. If a pending clawdy changeset exists, merge new changes into it via `ChangesetStore.merge_changes()`.

`merge_changes(changeset_id, new_changes)` matches by file path (`change.input["path"]`):
- **Path exists in current changes**: Update `proposed_content`, `original_content`, `diff`. Reset `status` to `"pending"` (force re-review since content changed). Keep same change ID.
- **Path is new**: Append as new `ProposedChange`.
- **Path in current but not in new**: Remove it (files are now identical, nothing to review).
- Update `updated_at` timestamp on the changeset (new field, separate from `created_at`).

If after merging there are zero changes remaining, delete the changeset.

### 2. Partition Diff Fix

All openclaw-originated diffs (files in `pull_changed`) go into the changeset. The existing auto-sync logic for user-originated changes (files not in `pull_changed`) stays unchanged. The key fix is that no diffs are silently dropped — they either go into the changeset or get auto-synced, never neither.

### 3. `useChangesetActions` Hook

Extracted from `ChangesetReview`. Owns all changeset mutation state and API calls.

**File**: `ui/src/hooks/useChangesetActions.ts`

**Input**:
- `changesetId: string`
- `initialChanges: ProposedChange[]`
- `sourceType: SourceType`
- `onDone: () => void`

**Returns**:
- `changes: ProposedChange[]`
- `setChangeStatus(changeId: string, status: "approved" | "rejected" | "pending"): void`
- `setAllStatuses(status: "approved" | "rejected"): void`
- `toggleChange(changeId: string): void`
- `handleApply(): Promise<void>`
- `handleReject(): Promise<void>`
- `handleEditChange(changeId: string, content: string): void`
- `applying: boolean`
- `statusError: string | null`
- `result: { applied: string[]; failed: { id: string; error: string }[] } | null`
- `savingIds: Set<string>`
- `editBuffers: Record<string, string>`
- `viewModes: Record<string, "diff" | "preview" | "edit">`
- `setViewMode(changeId: string, mode: "diff" | "preview" | "edit"): void`

**Convergence**: Both `handleApply` and `handleReject` sync to the copy vault whenever one is configured, regardless of `sourceType`. The hook fetches clawdy config to determine if a copy vault exists.

### 4. `FileExplorer` Component

**File**: `ui/src/components/FileExplorer.tsx`

**Props**:
- `changes: ProposedChange[]`
- `selectedId: string | null`
- `onSelect: (changeId: string) => void`

**Behavior**:
- Builds a folder tree from `change.input.path` values (e.g., `notes/papers/file.md` -> `notes/ > papers/ > file.md`)
- Folders are collapsible, expanded by default
- Each file row shows: file name + badge (`MOD` yellow, `NEW` green, `DEL` red) based on `tool_name`
- Clicking a file calls `onSelect`, highlights selected row with accent border/background
- Reviewed files (approved/rejected) show a subtle checkmark/cross icon with reduced opacity
- Header shows count: "3 to review / 2 reviewed" (pending vs approved+rejected)
- Fixed width panel (~250px), not percentage-based

### 5. `ChangesetDetailPage` Layout Redesign

The page switches layout based on `changes.length`:

**Single change** (`changes.length === 1`): Current layout — full-width diff/preview/edit with bottom action bar. Uses `ChangesetReview` (simplified with `useChangesetActions` hook).

**Multi-change** (`changes.length > 1`): Three-panel layout:

```
+------------------------------------------------------+
|  <- Back    Changeset Detail    [status] [cost] [del] |
+-------------+----------------------------------------+
|             |  file.md  [MOD]   [Approve] [Reject]   |
|  FileExplr  |----------------------------------------|
|  ~250px     |                                        |
|  fixed      |  Diff / Preview / Edit viewer          |
|             |  (selected file only)                  |
|             |                                        |
+-------------+----------------------------------------+
|  > Feedback & Actions (collapsed by default)         |
|    [Annotation input]  [Apply N Changes] [Reject]    |
+------------------------------------------------------+
```

- **Top bar**: Status badge, timestamp, source type tag, cost display, delete button, converge button (same as current).
- **Middle left**: `FileExplorer` — fixed 250px width.
- **Middle right**: Diff viewer header with file path, change type badge, view mode toggle (diff/preview/edit), per-file approve/reject buttons. Below header: `DiffViewer`, `MarkdownPreview`, or edit textarea based on mode.
- **Bottom**: Collapsible panel, collapsed by default. Contains `AnnotationFeedback`, bulk actions (Approve All / Reject All), Apply/Reject buttons.
- First file auto-selected on load.
- No draggable divider — fixed width explorer.

### 6. `ChangesetReview` Simplification

`ChangesetReview` is retained for the single-change case only. It uses `useChangesetActions` internally instead of managing its own state. The multi-change accordion rendering, `renderRow` for multiple files, and the pending/reviewed sections are removed — that's now handled by the page-level three-panel layout.

### 7. Convergence Generalization

Both `handleApply` and `handleReject` in `useChangesetActions` call convergence when a copy vault is configured:
- On apply: sync approved changes to copy vault (they're now in main, copy should match)
- On reject: sync rejected state to copy vault (revert copy to match main)

The hook reads copy vault config from the clawdy config endpoint. If no copy vault is configured, convergence is skipped silently.

**Non-clawdy convergence**: For zotero/taxonomy changesets, convergence means copying the newly created/modified files from main vault to copy vault so they stay in sync. This is a simpler operation than clawdy convergence (which also handles rejected changes by reverting copy vault files). The backend `POST /clawdy/converge/{id}` endpoint needs to be generalized or a new sync endpoint added that copies applied changes to the copy vault without the clawdy-specific rejected-change logic.

### 8. `updated_at` Field

Add `updated_at: str | None` to the `Changeset` model. Set on creation (same as `created_at`), updated by `merge_changes()`. Displayed in the UI alongside `created_at` when they differ ("Created X, updated Y").

## Files Changed

### Backend
- `src/db/changesets.py` — Add `merge_changes()` method, add `updated_at` column
- `src/clawdy/service.py` — Remove skip-if-pending, call `merge_changes()` when pending exists
- `src/models/changesets.py` — Add `updated_at` field to `Changeset`

### Frontend
- `ui/src/hooks/useChangesetActions.ts` — **New**. Extracted from `ChangesetReview`.
- `ui/src/components/FileExplorer.tsx` — **New**. Folder tree with change badges.
- `ui/src/pages/ChangesetDetailPage.tsx` — Three-panel layout for multi-change.
- `ui/src/components/ChangesetReview.tsx` — Simplified to single-change, uses hook.
- `ui/src/types.ts` — Add `updated_at` to `Changeset` type.

### Tests
- `tests/unit/test_clawdy_service.py` or `tests/integration/` — Test `merge_changes()` behavior (upsert, remove, status reset)
- `ui/src/__tests__/components/` — Tests for `FileExplorer` component
- Existing `ChangesetReview` tests updated for simplified component

## Out of Scope

- Drag-and-drop reordering of changes
- Multi-select in explorer
- Inline commenting on diff lines
- Search/filter within the explorer
