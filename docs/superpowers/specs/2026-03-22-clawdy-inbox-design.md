# Clawdy Inbox — Design Spec

## Summary

An external agent (OpenClaw) runs on a separate system and pushes changes to a copy of the user's Obsidian vault, tracked by a separate git repo. Vault-agent periodically polls this copy vault, diffs it against the main vault, and surfaces differences as changesets in a dedicated "Clawdy Inbox" UI. The user can approve, reject, edit, or request reformatting (local Claude re-generation) of each proposed change. After all changes in a changeset are resolved, both vaults converge to the same state.

## Core Concepts

- **Main vault** — the user's primary Obsidian vault, already configured in vault-agent
- **Copy vault** — a local git-tracked clone that OpenClaw pushes to; path stored in `SettingsStore`
- **Clawdy changeset** — a `Changeset` with `source_type="clawdy"`, produced by diffing the copy vault against the main vault
- **Convergence** — after changeset resolution, both vaults match: approved changes were applied to main, rejected changes are overwritten in copy vault from main

## Data Flow

```
OpenClaw pushes to copy vault (git)
         │
         ▼
ClawdyService polls (configurable interval, default 5min)
         │
         ├─ git pull on copy vault
         ├─ diff all .md files: copy vault vs main vault
         ├─ categorize: modified / created / deleted
         │
         ▼
Produce Changeset (source_type="clawdy")
  └─ one ProposedChange per changed file
     ├─ modified → tool_name="replace_note", diff of old vs new
     ├─ created  → tool_name="create_note", full content as diff
     └─ deleted  → tool_name="delete_note", original content shown
         │
         ▼
ChangesetStore (existing SQLite persistence)
         │
         ▼
UI: Clawdy Inbox page → ChangesetDetailPage (existing review UI)
  └─ per-change actions: approve, reject, edit, request reformatting
         │
         ▼
Apply changeset (existing apply_changeset pipeline)
  ├─ replace_note → overwrite main vault file with proposed content
  ├─ create_note  → create new file in main vault (existing)
  └─ delete_note  → remove file from main vault
         │
         ▼
Convergence step (after all changes resolved)
  ├─ rejected modified → copy main vault file content to copy vault
  ├─ rejected created  → delete file from copy vault
  ├─ rejected deleted  → copy main vault file to copy vault
  └─ git commit + push on copy vault
```

## Model Adaptations

### `Changeset.items` field

The existing `Changeset.items` is `list[ContentItem]` (required, no default). ContentItem represents extracted text from Zotero/web sources — clawdy changesets have no such origin content. Make `items` optional with a default empty list: `items: list[ContentItem] = Field(default_factory=list, ...)`. This is backwards-compatible — existing changesets always populate it, clawdy changesets pass an empty list.

### `Changeset.routing` field

`RoutingInfo` is agent-specific (action, confidence, reasoning). Clawdy changesets set `routing=None` — the field is already optional.

### `SourceType` update

`SourceType` is defined in `src/models/content.py` as `Literal["web", "zotero", "book"]`. Add `"clawdy"` to this shared literal — it's used by both `ContentItem.source_type` and `Changeset.source_type`.

### `ProposedChange` for delete operations

`ProposedChange.proposed_content` is a required `str` field. For `delete_note` changes, set `proposed_content` to an empty string `""`. The diff will show the full original content as removed lines. The DiffViewer handles this naturally — it renders the diff string, which will show all lines as deletions.

### `Changeset` fields for clawdy

- `items`: empty list `[]` (field made optional with default)
- `routing`: `None` (already optional)
- `reasoning`: static string, e.g. `"Changes detected from OpenClaw sync"` — set by `ClawdyService` during changeset creation

### New tool input models

Add to `src/models/tools.py` alongside existing `CreateNoteInput` and `UpdateNoteInput`:
- `ReplaceNoteInput` — `path: str`, `content: str` (max 200k)
- `DeleteNoteInput` — `path: str`

`apply_changeset()` constructs these from `change.input` the same way it handles existing input types.

### Write policy expansion

The project convention is "additive-only writes" (create + append). This feature deliberately expands the write policy to include `replace_note` and `delete_note`, scoped exclusively to clawdy changeset application and convergence. These operations are never exposed as general-purpose vault writer functions — they are only invoked through the changeset apply pipeline when `source_type="clawdy"`. The existing Zotero/migration flows remain additive-only.

## Backend

### New module: `src/clawdy/`

#### `src/clawdy/service.py` — ClawdyService

Core engine. Manages the poll loop, diffing, changeset creation, and convergence.

**Poll loop:**
- Runs as a background `asyncio.Task` started in FastAPI lifespan
- Configurable interval (default 300s), stored in `SettingsStore` as `clawdy_interval`
- Skips poll if disabled (`clawdy_enabled` setting) or if a pending clawdy changeset already exists
- On error (git pull failure, etc.), logs and skips cycle; surfaces error via status endpoint

**Diffing:**
- Iterates all `.md` files in both vaults using `iter_markdown_files()`
- Compares file content directly (not git diff — we diff repo state against main vault state)
- Produces three lists: modified, created (in copy but not main), deleted (in main but not copy)
- Uses existing `generate_diff()` for each file pair

**Changeset creation:**
- One `Changeset` per poll cycle that detected changes
- One `ProposedChange` per changed file
- `tool_name` values: `replace_note` (modified), `create_note` (new), `delete_note` (removed)
- Each `ProposedChange` includes `original_content`, `proposed_content`, and `diff`

**Convergence:**
- Triggered explicitly via a "Finalize & Sync" button on the ChangesetDetailPage (visible only for clawdy changesets). The button is enabled when all changes have a terminal status (applied or rejected) — no pending changes remain.
- The button calls `POST /clawdy/converge/{changeset_id}`, which:
  1. Verifies all changes are in terminal state
  2. For rejected changes: overwrites copy vault files with main vault content (or creates/deletes as needed)
  3. Commits and pushes to copy vault repo so OpenClaw starts from a clean baseline
  4. Sets changeset status to `applied` (if any approved) or `rejected` (if all rejected)
- This avoids implicit triggers and gives the user control over when convergence happens

#### `src/clawdy/git.py` — Git operations

Thin wrapper around `subprocess.run` for git commands. All functions take `repo_path` as first arg.

- `pull(repo_path)` — `git pull` with error handling
- `commit(repo_path, message)` — `git add -A && git commit -m message`
- `push(repo_path)` — `git push`
- `is_git_repo(repo_path)` — validates `.git` directory exists
- `status(repo_path)` — `git status --porcelain` for checking dirty state

#### `src/clawdy/__init__.py` — Exports

### Changes to existing backend code

**`src/models/changesets.py`:**
- Add `"clawdy"` to valid `source_type` values
- Add `"replace_note"` and `"delete_note"` to valid `tool_name` values on `ProposedChange`

**`src/agent/changeset.py` — `apply_changeset()`:**
- Handle `replace_note`: read file at `change.input["path"]`, overwrite with `change.proposed_content`
- Handle `delete_note`: remove file at `change.input["path"]` using `validate_path()` for safety

**`src/vault/writer.py`:**
- Add `replace_note(vault_path, path, content)` — validates path, overwrites file
- Add `delete_note(vault_path, path)` — validates path, removes file

**`src/server.py`:**
- Add lifespan hook to start/stop `ClawdyService` background task
- Add `/clawdy/*` route group
- Hook convergence into changeset apply/reject flow when `source_type="clawdy"`

### API Endpoints

```
GET  /clawdy/config              — read config (copy_vault_path, interval, enabled)
PUT  /clawdy/config              — update config (validates path is a git repo)
GET  /clawdy/status              — sync state (enabled, last_poll, next_poll, error, pending_changeset_count)
POST /clawdy/trigger             — manually trigger poll+diff cycle
POST /clawdy/converge/{id}       — run convergence on a fully-resolved changeset (sync rejections back, commit, push)
```

**Changeset filtering:** Add `source_type` query param to existing `GET /changesets` endpoint. The `get_all_filtered()` store method gains an optional `source_type` parameter. Server-side filtering — not client-side. This benefits the Clawdy Inbox page and is also generally useful for other source types.

Changeset review uses existing `/changesets/*` endpoints unchanged.

### Regeneration (request reformatting)

Uses existing changeset regeneration flow. When user requests reformatting on a clawdy change:
1. Takes the `proposed_content` + user feedback text
2. Makes a Claude call to reformat (same pattern as Zotero changeset regeneration)
3. Updates `ProposedChange` with new content, recalculates diff
4. User reviews the reformatted version

## Frontend

### New route: `/clawdy`

Added to router inside the Layout wrapper. New sidebar nav item "Clawdy Inbox".

### New page: `ClawdyInboxPage.tsx`

**Top section — Status & Config:**
- Copy vault path display with file picker button to change
- Sync status: last poll time, next poll countdown, error state
- Enable/disable toggle
- Poll interval selector (1min, 5min, 15min, 30min)
- "Check Now" button → `POST /clawdy/trigger`

**Below — Changeset list:**
- Fetches changesets filtered to `source_type="clawdy"` via existing `GET /changesets?source_type=clawdy`
- Same card layout as `ChangesetsPage` (status badge, change count, timestamp, file list preview)
- Clicking a changeset navigates to existing `/changesets/:id` → `ChangesetDetailPage`

### Changes to existing frontend

**`Sidebar.tsx`:**
- Add "Clawdy Inbox" to `NAV_ITEMS`

**`router.tsx`:**
- Add `/clawdy` route → `ClawdyInboxPage`

**`ChangesetsPage.tsx`:**
- Add `source_type` filter parameter to `GET /changesets` (if not already supported)
- Clawdy changesets appear here too with a "clawdy" badge, but the dedicated page is the primary entry point

**`ChangesetDetailPage.tsx`:**
- For clawdy changesets, after all changes are resolved → trigger convergence via existing apply/reject callbacks
- No structural changes to the review UI itself

**`api/client.ts`:**
- Add `getClawdyConfig()`, `updateClawdyConfig()`, `getClawdyStatus()`, `triggerClawdySync()` functions

**`types.ts`:**
- Add `ClawdyConfig`, `ClawdyStatus` interfaces

## Error Handling

| Error | Behavior |
|-------|----------|
| Copy vault path invalid / not a git repo | Validation error on config save; UI shows error state |
| `git pull` fails (network, conflict) | Log error, show in status UI, skip poll cycle, retry next interval |
| No changes detected | Silent skip, no changeset created |
| Pending clawdy changeset exists | Skip poll, avoid flooding with duplicates |
| Convergence push fails | Show error in status UI, retry on next manual trigger or poll |
| File read/write errors during diff | Per-file error logged, other files still processed |

## Testing

### Backend

**Unit tests (`tests/unit/`):**
- `test_clawdy_git.py` — git wrapper functions with mock subprocess
- `test_clawdy_service.py` — diff logic, changeset creation, convergence logic (using temp directories, no actual git)

**Integration tests (`tests/integration/`):**
- `test_clawdy_routes.py` — API endpoint tests with `:memory:` stores
- `test_clawdy_apply.py` — `replace_note` and `delete_note` through `apply_changeset()`

### Frontend

**Component tests:**
- `ClawdyInboxPage.test.tsx` — status display, config editing, changeset list rendering, manual trigger

**MSW handlers:**
- Add `/clawdy/*` mock handlers

### E2E

- `clawdy.spec.ts` — config flow, changeset review flow with mocked API

## File Structure (new files only)

```
src/clawdy/
├── __init__.py
├── service.py      # ClawdyService: poll loop, diff, changeset creation, convergence
└── git.py          # Thin git subprocess wrapper

ui/src/pages/
└── ClawdyInboxPage.tsx

tests/unit/
├── test_clawdy_git.py
└── test_clawdy_service.py

tests/integration/
├── test_clawdy_routes.py
└── test_clawdy_apply.py

ui/src/__tests__/components/
└── ClawdyInboxPage.test.tsx

tests/e2e/specs/
└── clawdy.spec.ts
```

## Resolved Questions

- **Changeset filtering:** Server-side. `GET /changesets` gains a `source_type` query param. The `source_type` is stored inside the JSON `data` column, not a dedicated column. Add a `source_type TEXT` column to the `changesets` table (populated on insert from the changeset data) for efficient filtering, avoiding `json_extract()` on every query. Backfill existing rows with `"web"` or extract from JSON.
- **Convergence commit message:** Yes — include a summary like "vault-agent: applied 3, rejected 2 changes" with the list of affected file paths.
- **Poll pause during review:** No additional logic beyond "skip if pending changeset exists." A pending changeset already blocks new ones. Once resolved + converged, the next poll can proceed.
- **Max file size for diffing:** No threshold. All `.md` files are diffed. Obsidian vaults don't typically have enormous markdown files.
