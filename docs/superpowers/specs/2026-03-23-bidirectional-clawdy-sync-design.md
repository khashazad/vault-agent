# Bidirectional Clawdy Sync

## Problem

Clawdy syncs one direction: copy vault → main vault. OpenClaw edits the copy vault, Clawdy detects diffs, user reviews/approves. But when the user edits the main vault directly, those changes don't propagate to the copy vault. The vaults drift apart silently.

## Goal

Auto-sync main→copy so both vaults stay in lockstep. No user intervention for user-originated changes.

## Approach: Pre/Post Pull Snapshots

After convergence, both vaults are identical. Any subsequent difference can be attributed by comparing the copy vault before and after `git pull`:

- Files changed during pull → **OpenClaw** edits → changeset for review (existing behavior)
- Files that differ but copy didn't change during pull → **user** edited main vault → auto-sync to copy (new)

### Safety Guard

Bidirectional sync activates only after the first successful convergence, tracked via `clawdy_last_converge` timestamp in SettingsStore. Before that, ALL differences go through changeset review. This prevents destructive auto-sync when vaults have pre-existing unknown differences.

No toggle to disable — always on once convergence has happened. Changing `copy_vault_path` resets the guard (deletes `clawdy_last_converge`), requiring re-convergence.

## Detailed Design

### New Functions (`src/clawdy/service.py`)

#### `snapshot_vault(vault_path: str) -> dict[str, str]`

MD5 hash all `.md` files using `iter_markdown_files()` from `src/vault/__init__.py`. Returns `{relative_path: hex_digest}`. This is a fast operation — only reads file bytes for hashing, no parsing.

#### `partition_diff(modified, created, deleted, pull_changed) -> tuple[tuple, tuple]`

Pure function. Splits each diff list by membership in `pull_changed` set.

**Input:**
- `modified: list[FileChange]`, `created: list[FileCreate]`, `deleted: list[FileDelete]` — from `diff_vaults()`
- `pull_changed: set[str]` — relative paths whose hash changed between pre/post pull snapshots

**Output:** `(openclaw_diffs, main_diffs)` where each is a `(modified, created, deleted)` tuple.

**Attribution logic:**
- File in `pull_changed` → OpenClaw change
- File NOT in `pull_changed` → user (main vault) change

#### `sync_main_to_copy(main_vault, copy_vault, modified, created, deleted) -> int`

Writes main vault state to copy vault for user-originated changes:

- `modified` (both have file, copy unchanged by pull) → overwrite copy with main content
- `created` from diff perspective (file exists in copy but not main, copy unchanged by pull) → user deleted from main → delete from copy
- `deleted` from diff perspective (file exists in main but not copy, copy unchanged by pull) → user created in main → create in copy

Returns count of files synced. Creates parent directories as needed.

### Refactored Function

#### `create_clawdy_changeset(main_vault, copy_vault, diffs=None)`

Add optional `diffs` parameter: `tuple[list[FileChange], list[FileCreate], list[FileDelete]] | None`.

When provided, skip internal `diff_vaults()` call and use supplied diffs. When `None` (default), call `diff_vaults()` as before. Backward compatible — existing callers unaffected.

### Modified `ClawdyService.poll()`

New flow:

```
1. Early exits (disabled, no copy_vault, pending changeset) — unchanged
2. snapshot_before = snapshot_vault(copy_vault)
3. git pull (failure → set last_error, return)
4. snapshot_after = snapshot_vault(copy_vault)
5. pull_changed = {paths where hash differs between snapshots}
6. modified, created, deleted = diff_vaults(main, copy)
7. openclaw_diffs, main_diffs = partition_diff(modified, created, deleted, pull_changed)
8. If clawdy_last_converge exists AND main_diffs has changes:
     count = sync_main_to_copy(main, copy, *main_diffs)
     if count > 0:
       git commit + push (best-effort; failure logged to last_error, does not block)
     self.last_auto_sync = count
9. create_clawdy_changeset(main, copy, diffs=openclaw_diffs)
```

New instance attribute: `last_auto_sync: int | None` — count of files synced in most recent poll. `None` if no auto-sync attempted.

### Failure Handling

Auto-sync git push failure:
- Log error to `last_error`
- Proceed with OpenClaw changeset creation (independent)
- Next poll retries naturally since `diff_vaults` will still detect the divergence
- UI already renders `last_error`

### Server Route Changes (`src/server.py`)

**`POST /clawdy/converge/{changeset_id}`** — after successful git push, write timestamp:
```python
get_settings_store().set("clawdy_last_converge", datetime.now(timezone.utc).isoformat())
```

**`PUT /clawdy/config`** — when `copy_vault_path` changes, delete `clawdy_last_converge`:
```python
if req.copy_vault_path is not None:
    get_settings_store().delete("clawdy_last_converge")
```

**`GET /clawdy/status`** — add two fields to response:
- `last_auto_sync`: from `ClawdyService.last_auto_sync`
- `bidirectional_enabled`: `True` if `clawdy_last_converge` exists in SettingsStore

### Model Changes (`src/models/vault.py`)

`ClawdyStatusResponse` — add:
```python
last_auto_sync: int | None
bidirectional_enabled: bool
```

### TypeScript Changes (`ui/src/types.ts`)

`ClawdyStatus` — add:
```typescript
last_auto_sync: number | null;
bidirectional_enabled: boolean;
```

### UI Changes (`ui/src/pages/ClawdyInboxPage.tsx`)

Two extra `<span>` elements in the existing status bar:
- Bidirectional indicator: "Bidirectional" in green when `bidirectional_enabled`, absent otherwise
- Last auto-sync count: "Auto-synced N files" when `last_auto_sync` is non-null and > 0

### Tests

**Unit (`tests/unit/test_clawdy_service.py`):**

`TestSnapshotVault`:
- Hashes `.md` files correctly
- Ignores non-`.md` files
- Empty vault returns empty dict

`TestPartitionDiff`:
- Separates pull-changed files into OpenClaw tuple
- Non-pull-changed files go to main tuple
- Empty `pull_changed` → everything is main
- All in `pull_changed` → everything is OpenClaw

`TestSyncMainToCopy`:
- Modified files → overwrite copy with main content
- Created-only-in-copy files → delete from copy
- Deleted-from-copy files → create in copy from main
- Returns correct count
- Skips files in `pull_changed` (handled by partition_diff, but verify integration)

`TestClawdyServicePoll` additions:
- With `last_converge` set: auto-syncs user changes, commits+pushes
- Without `last_converge`: no auto-sync, all diffs go to changeset
- Auto-sync commit+push failure: logged, changeset still created
- Zero files synced: no git commit

**Integration (`tests/integration/test_clawdy_routes.py`):**

- `test_converge_sets_last_converge_timestamp`: POST converge → verify SettingsStore has `clawdy_last_converge`
- `test_status_includes_bidirectional_fields`: GET status → verify `last_auto_sync` and `bidirectional_enabled` present
- `test_config_change_resets_last_converge`: PUT config with new `copy_vault_path` → verify `clawdy_last_converge` deleted

## Files Modified

| File | Change |
|------|--------|
| `src/clawdy/service.py` | Add `snapshot_vault`, `partition_diff`, `sync_main_to_copy`; refactor `create_clawdy_changeset`; rewrite `poll()` |
| `src/server.py` | Converge route sets timestamp; config route resets timestamp; status route adds fields |
| `src/models/vault.py` | Two fields on `ClawdyStatusResponse` |
| `ui/src/types.ts` | Two fields on `ClawdyStatus` |
| `ui/src/pages/ClawdyInboxPage.tsx` | Two spans in status bar |
| `tests/unit/test_clawdy_service.py` | New test classes + poll test additions |
| `tests/integration/test_clawdy_routes.py` | Three new integration tests |

## Out of Scope

- Conflict resolution (same file edited on both sides between polls) — partition_diff sends conflicts to OpenClaw (changeset review), which is the safe default
- Non-`.md` file sync (e.g. attachments, `.obsidian/` config)
- Settings toggle to disable bidirectional sync
