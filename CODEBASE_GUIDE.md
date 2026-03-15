k# Codebase Navigation Guide

Ordered reading path — each file builds on what you've already seen. No forward references.

---

## Layer 0: Data Shape

Everything else manipulates these types. Read first.

### 1. `src/models/content.py`
The atomic unit. `ContentItem` = one highlighted passage + source metadata. `SourceType` is a Literal enum (`"web" | "zotero" | "book"`). `SourceMetadata` carries optional fields for DOI, authors, year, etc.

**Look for**: The `max_length` validators on `text` (50k) and `source` (2k) — these guard against LLM context overflow.

### 2. `src/models/vault.py`
How the Obsidian vault is represented in memory. Three tiers:
- `VaultNoteSummary` — lightweight (path, title, wikilinks, headings)
- `VaultNote` — full (frontmatter dict + content)
- `VaultMap` — entire vault structure, including `as_string` for LLM context

**Look for**: `as_string` on `VaultMap` — the vault reader builds this as a folder tree + note listings that the LLM reads to decide where to place new notes.

### 3. `src/models/tools.py`
Shapes for write operations: `CreateNoteInput`, `UpdateNoteInput`, `ReadNoteInput`. These define what the agent can ask the vault to do.

**Look for**: `UpdateNoteInput.operation` field — supports `"append_to_heading"` and `"append_to_end"` operations.

### 4. `src/models/changesets.py`
The core abstraction. This is where the approval workflow lives.

- `ProposedChange` — single file operation (create or update), with diff and status tracking
- `Changeset` — collection of changes + reasoning, routing, token usage, feedback
- `RoutingInfo` — the agent's decision about where to place the note (action, target_path, confidence)
- `TokenUsage` — cost tracking (input/output/cache tokens, model, USD cost)

**Look for**: `ChangesetStatus` progression: `pending → applied | rejected | partially_applied | skipped | revision_requested`. The `@model_validator` for backwards-compatibility migration (`highlights → items`).

### 5. `src/models/zotero.py`
Request/response types for all Zotero endpoints. `ZoteroPaperSummary` carries sync metadata (last_synced, changeset_id) for the UI. `ZoteroPaperSyncRequest` supports `batch: true` for Batch API.

**Look for**: `ZoteroPapersResponse.cache_updated_at` — drives the "last refreshed" display in the UI.

### 6. `src/models/__init__.py`
Re-exports. Skim to see what's public — everything is re-exported from the submodules.

---

## Layer 1: Configuration & Storage

### 7. `src/config.py`
`AppConfig` dataclass loads from environment. `load_config()` validates that `VAULT_PATH` exists and is a directory.

**Look for**: Zotero fields are optional — the app runs without Zotero configured (endpoints return 400 if credentials missing).

### 8. `src/store.py`
SQLite with WAL journal mode. Two stores:
- `ChangesetStore` — upserts changeset JSON, supports filtered queries with status/offset/limit
- `BatchJobStore` — tracks async Batch API jobs per paper_key

**Look for**: The lazy singleton pattern — `_changeset_store = None` at module level, `get_changeset_store()` initializes on first call. Tests reset this global to inject `:memory:` SQLite. This is the key testability seam.

---

## Layer 2: Vault I/O

### 9. `src/vault/__init__.py`
`validate_path()` prevents directory traversal — resolves the path against vault root and checks it stays within bounds. `iter_markdown_files()` yields all `.md` files, skipping symlinks and hidden dirs.

**Look for**: The `.resolve()` call and `is_relative_to()` check — this is the security boundary.

### 10. `src/vault/reader.py`
Transforms the filesystem into data the LLM can consume.

- `parse_frontmatter()` — splits YAML from body using `python-frontmatter`
- `extract_wikilinks()` — regex `\[\[([^\]|]+)(?:\|[^\]]+)?\]\]`, dedup-preserving order
- `extract_headings()` — regex for `#{1,6}` lines
- `build_vault_map()` — scans all `.md` files, builds `VaultMap` with folder tree string
- `format_vault_summary()` — compact format for >200 notes, detailed for small vaults

**Look for**: The compact vs detailed format split in `format_vault_summary()` — large vaults get a condensed folder tree while small vaults get full note listings with headings.

### 11. `src/vault/writer.py`
Additive-only writes. Two operations:
- `create_note()` — exclusive open mode `'x'` (atomic fail if file exists)
- `update_note()` — reads, computes append, writes back

**Look for**: `compute_create()` and `compute_update()` are pure functions that return the proposed content string. The actual I/O is separate. `update_note` uses `compute_update` which finds the target heading and appends below it.

---

## Layer 3: Agent (AI Synthesis Core)

### 12. `src/agent/prompts.py`
Where the LLM's behavior is defined.

- `COLOR_SEMANTICS` — maps hex colors to priority labels (`#ff6666 → Critical`, `#ffd400 → Important`)
- `ZOTERO_PAPER_TEMPLATE` — the expected note structure
- `build_zotero_synthesis_prompt()` → `(system, user)` message pair

**Look for**: The system prompt instructs the LLM to return raw markdown only (no tool calls, no JSON). User message includes color-labeled annotations + optional feedback for regeneration.

### 13. `src/agent/agent.py`
Single Claude call, no tool loop. ~40 lines of core logic.

- `generate_zotero_note()` — the main function. Flow: build prompt → call API → parse response → wrap in `ProposedChange` → build `Changeset` → persist to store
- `_create_with_retry()` — exponential backoff on 429/529 (max 3 retries, 1s base)
- `_compute_cost()` — USD calculation with per-model pricing table and batch discount
- `_zotero_note_path()` — derives `Papers/{sanitized-title}.md` from metadata

**Look for**: `cache_control: {"type": "ephemeral"}` on the system prompt — enables Anthropic prompt caching. The batch API path (`submit_zotero_note_batch` / `poll_zotero_batch`) for 50% cost reduction.

### 14. `src/agent/diff.py`
Thin wrapper around `difflib.unified_diff()`. `generate_diff(path, original, proposed)` returns a unified diff string. Used both for display in UI and storage in changesets.

### 15. `src/agent/changeset.py`
`apply_changeset()` dispatches approved changes to the vault writer. Iterates `changeset.changes`, checks status, calls `create_note()` or `update_note()` based on `tool_name`. Returns `{applied: [...], failed: [...]}`.

**Look for**: Error handling per-change — one failed write doesn't abort the rest.

### 16. `src/agent/wikify.py`
Post-processing auto-linker: scans vault map titles, wraps first occurrence in `[[wikilinks]]`.

- `_find_protected_spans()` — collects spans that shouldn't be modified (frontmatter, code blocks, existing wikilinks, headings)
- `wikify()` — builds targets from note titles + headings, sorted longest-first, case-insensitive regex match, replaces first occurrence only

**Look for**: The longest-first sorting prevents partial matches (e.g., "Machine Learning" matches before "Machine"). Protected spans prevent double-linking existing wikilinks.

---

## Layer 4: Zotero Integration

### 17. `src/zotero/client.py`
Wraps `pyzotero`. Core data classes: `ZoteroPaper`, `ZoteroAnnotation`, `ZoteroPaperMetadata`, `ZoteroCollectionInfo`.

- `fetch_annotations_grouped()` — the key method. Three-hop resolution: annotation → attachment → paper. Groups annotations by parent paper.
- `fetch_papers()` — top-level items, excludes children
- `fetch_paper_annotations()` — traverses paper's children tree to find PDF attachments and their annotations
- `count_annotations_per_paper()` — bulk fetch for the papers list UI

**Look for**: The parent resolution in `fetch_annotations_grouped()` — annotations live on PDF attachments, not directly on papers. Requires two hops (annotation → attachment → paper) to group correctly.

### 18. `src/zotero/sync.py`
`ZoteroSyncState` — SQLite-backed state across 4 tables:
- `zotero_sync_state` — global sync version + last_synced timestamp
- `zotero_paper_sync` — per-paper sync tracking (last_synced, changeset_id)
- `zotero_papers` — paper cache (title, authors, DOI, etc.)
- `zotero_collections` — collection cache

**Look for**: `get_cached_papers_paginated()` supports search (LIKE on title/authors), sync_status filtering (cross-references `zotero_paper_sync` table), and offset/limit pagination.

### 19. `src/zotero/orchestrator.py`
`sync_zotero()` — the coordination function.

Flow: fetch papers from Zotero → filter → convert annotations to `ContentItem` list → call `generate_zotero_note()` per paper → record library version.

**Look for**: `_paper_to_content_items()` — converts `ZoteroAnnotation` objects to `ContentItem` objects, combining comment + page_label into the annotation field.

### 20. `src/zotero/background.py`
`ZoteroPaperCacheSyncer` — async background task with event-driven trigger. `trigger_sync()` sets an asyncio.Event to wake the loop. `_do_sync()` refreshes paper + collection caches, deletes stale entries.

**Look for**: The event-driven pattern — the loop waits on `self._event.wait()` instead of polling on a timer. UI triggers refresh via `POST /zotero/papers/refresh`.

---

## Layer 5: Server (HTTP Surface)

### 21. `src/server.py`
Read last — everything connects here.

- `lifespan()` — loads config, starts/stops `paper_cache_syncer`
- `_get_config(request)` — retrieves from `app.state` (deferred config pattern)
- `_require_zotero(request)` — guard for Zotero endpoints
- `_handle_anthropic_error()` — maps SDK exceptions to HTTP status codes

**Routes** (~18 endpoints across 4 tags):
- **Health**: `GET /health`
- **Vault**: `GET /vault/map`
- **Changesets**: CRUD + apply/reject/request-changes/regenerate
- **Zotero**: papers list, annotations, sync, collections, cache management, batch status

**Look for**: The `batch: true` path in paper sync — submits to Anthropic Batch API, returns 202 with batch_id. Separate polling endpoint finalizes the changeset. The regenerate endpoint chains to the original changeset via `parent_changeset_id`.

---

## Layer 6: Frontend

### 22. `ui/src/types.ts`
TypeScript mirrors of the Python Pydantic models. Compare with `src/models/` to see the 1:1 mapping.

### 23. `ui/src/api/client.ts`
Thin fetch wrapper. All calls use relative URLs (proxied in dev). One function per endpoint.

**Look for**: `updateChangeContent()` — sends edited content back to server, which recalculates the diff.

### 24. `ui/src/utils/obsidian.ts`
`preprocessObsidian()` converts Obsidian syntax to HTML spans:
- `![[Note]]` → embed span
- `[[Note]]` → wikilink span
- `#tag` → tag span

`extractFrontmatter()` — simple YAML parser (no dependency on a YAML library).

### 25. `ui/src/utils/diff.ts`
`computeLines()` — produces diff lines from content or fallback unified diff. `groupLines()` — collapses context sections (>6 lines → show 3/collapse/show 3).

### 26-27. `ui/src/main.tsx` → `ui/src/App.tsx` → `ui/src/components/Layout.tsx`
Entry point → root component → shell. `App` manages `tab` state (`"sync" | "history"`). Layout renders header with tab buttons + content area.

### 28. `ui/src/components/CollectionTree.tsx`
`buildTree()` converts flat collection list to nested tree. Recursive `TreeNodeItem` renders expand/collapse with depth-based indentation.

### 29. `ui/src/components/ZoteroSync.tsx`
The biggest component. 3-step state machine: `papers → annotations → processing`.

- **Papers**: collection sidebar + paper list with search, sync-status filter, pagination
- **Annotations**: grouped by color, checkbox selection, model dropdown (Haiku/Sonnet)
- **Processing**: calls `syncZoteroPaper()`, renders `ChangesetReview`

**Look for**: The debounced search (300ms), polling cache refresh (3s interval), and grouped annotations memoization.

### 30. `ui/src/components/DiffViewer.tsx`
Uses `computeLines()` + `groupLines()`. `CollapsedSection` expands on click. Each `DiffRow` shows old/new line numbers + colored content.

### 31. `ui/src/components/MarkdownPreview.tsx`
`react-markdown` + `rehype-raw` + custom callout handling. Renders Obsidian syntax via `preprocessObsidian()` which outputs HTML spans that rehype-raw passes through.

### 32. `ui/src/components/ChangesetReview.tsx`
Three view modes per change: `diff | preview | edit`. Auto-approves all changes on load. Edit mode uses 500ms debounce → sends content to server → refetches changeset with updated diff.

### 33. `ui/src/components/AnnotationFeedback.tsx`
Text selection capture (`window.getSelection()`) + comment input. `formatAnnotations()` serializes for the API.

### 34. `ui/src/components/ChangesetHistory.tsx`
List/detail views with resizable split panel (mouse drag, 40-85% constraint). Detail view shows metadata, routing, cost, and either interactive review or read-only view depending on changeset status.

### 35. `ui/src/components/ErrorAlert.tsx`
Red box with "Error:" label + message.

---

## Layer 7: Tests (Optional)

### 36. `tests/conftest.py` + `tests/factories.py`
Root fixtures: `tmp_vault` creates temp dir with sample notes. Factories: `make_content_item()`, `make_changeset()`, etc. with `**overrides`.

### 37. `tests/integration/conftest.py`
`:memory:` SQLite injection — resets the global singleton in `store.py` and creates a fresh in-memory store per test.

### 38. `ui/src/__tests__/setup.ts` + `ui/src/__tests__/handlers.ts`
MSW (Mock Service Worker) intercepts all fetch calls with canned responses. Tests override specific handlers via `server.use()`.
