# AGENTS.md — Vault Agent

## Project Overview

A **FastAPI + React** application that manages an Obsidian vault through three core capabilities:

1. **Zotero Sync** — Fetches Zotero annotations, synthesizes them into Obsidian-compatible paper notes via a single Codex LLM call, and writes to the vault after user approval.
2. **Vault Migration** — Job-based async system that transforms every note in a vault according to a curated taxonomy. Supports per-note LLM calls with prompt caching, Anthropic Batch API (50% cost), and cost estimation.
3. **Vault Taxonomy** — Scans vault structure (tags, link targets, folders), supports curation operations (rename/merge/delete), and produces changesets for review before applying.

Vault configuration is UI-driven: users select a vault folder via a native file picker, persisted in SQLite (not env var).

## Architecture

```
Zotero Sync Flow:
  POST /zotero/papers/{paper_key}/sync
    → Fetch annotations from Zotero API
    → Build ContentItem list from annotations
    → Single Codex LLM call synthesizes annotations into a paper note
    → Proposed note wrapped in a Changeset with diff (persisted in SQLite)
    → Response: full Changeset with diff and routing info

Migration Flow:
  POST /migration/taxonomy/import → validate + store taxonomy proposal
  PUT /migration/taxonomy/{id}    → curate (edit folders/tags/links)
  POST /migration/taxonomy/{id}/activate → set as active taxonomy
  POST /migration/jobs            → scan vault, create MigrationNote per file
  POST /migration/estimate        → estimate token cost before running
  run_migration() or submit_migration_batch()
    → Per-note LLM call with taxonomy-driven system prompt (cached)
    → Parses MIGRATION_META (target_folder, new_link_targets)
    → Generates diff, sets note status to "proposed"
  POST /migration/jobs/{id}/apply → write approved notes to target vault

Taxonomy Flow:
  GET /vault/taxonomy
    → Single-pass scan: extract tags, wikilinks, folders from all .md files
    → Build tag hierarchy from slash-separated names
    → Return VaultTaxonomy (folders, tags, hierarchy, link_targets, total_notes)
  POST /vault/taxonomy/apply
    → Apply TaxonomyCurationOp list (rename/merge/delete for tags, links, folders)
    → Return Changeset with ProposedChange per affected note

Vault Config Flow:
  POST /vault/picker → native file dialog → path
  PUT /vault/config  → persist path in SettingsStore (SQLite)
  GET /vault/config  → read from SettingsStore → app.state.config

Clawdy Inbox Flow:
  ClawdyService polls copy vault on interval (default 5min)
    → git pull on copy vault
    → diff_vaults() compares all .md files between main and copy vault
    → Creates Changeset with source_type="clawdy" (replace_note, create_note, delete_note)
    → User reviews in ClawdyInboxPage, approves/rejects per change
  POST /clawdy/converge/{id}
    → converge_vaults() syncs rejected changes back to copy vault
    → git commit + push on copy vault

Changeset Apply (shared across all flows):
  PATCH /changesets/{id}/changes/{change_id} → approve/reject individual changes
  POST /changesets/{id}/apply → write approved changes to vault filesystem
```

### Key Modules

- **`src/server.py`** — FastAPI entry point. 42 route definitions, CORS middleware, exception handler, lifespan config loading.
- **`src/config.py`** — `AppConfig` dataclass. Loads `vault_path` from DB via `SettingsStore` (not env var). `ANTHROPIC_API_KEY` and Zotero keys from env.
- **`src/logging_config.py`** — Rich-based logging setup. Routes uvicorn logs through `RichHandler`.
- **`src/models/`** — Pydantic models split into `content.py`, `changesets.py`, `vault.py`, `tools.py`, `zotero.py`, `migration.py`.
- **`src/db/`** — SQLite stores (WAL mode), all lazy singletons in `__init__.py`:
  - `ChangesetStore` — changeset + proposed change CRUD
  - `BatchJobStore` — Zotero batch job tracking
  - `MigrationStore` — migration jobs, notes, taxonomy proposals
  - `SettingsStore` — key-value config persistence (vault_path, etc.)
- **`src/vault/reader.py`** — Scans vault filesystem. Parses frontmatter, extracts wikilinks, builds vault map for LLM context.
- **`src/vault/writer.py`** — Additive-only filesystem writes: create note, append section.
- **`src/vault/taxonomy.py`** — `build_vault_taxonomy()` single-pass scan; `apply_taxonomy_curation()` for rename/merge/delete operations.
- **`src/vault/__init__.py`** — `validate_path()` preventing traversal; `iter_markdown_files()` yielding all `.md` files.
- **`src/agent/agent.py`** — Single-call Zotero note synthesis (`generate_zotero_note`), batch API support, cost tracking.
- **`src/agent/prompts.py`** — Zotero synthesis prompt builder. Produces (system, user) pair from annotations and metadata.
- **`src/agent/utils.py`** — Model pricing table (`MODELS`), `DEFAULT_MODEL = "sonnet"`, `compute_cost()`, `create_with_retry()` with exponential backoff, `extract_usage()`.
- **`src/agent/changeset.py`** — `apply_changeset()`. Dispatches approved `ProposedChange` objects to `create_note` / `update_note`.
- **`src/agent/diff.py`** — `generate_diff()` wrapping `difflib.unified_diff`.
- **`src/agent/wikify.py`** — Post-processing wikilink auto-linker.
- **`src/zotero/client.py`** — Zotero API client wrapping `pyzotero`.
- **`src/zotero/sync.py`** — Annotation → `ContentItem` conversion and agent invocation.
- **`src/zotero/orchestrator.py`** — Coordination layer for Zotero sync operations.
- **`src/zotero/background.py`** — Background paper cache refresh.
- **`src/migration/migrator.py`** — Core migration engine: `estimate_cost()`, `migrate_note()`, `run_migration()` (concurrent, semaphore=5), `create_migration_job()`, `submit_migration_batch()`, `poll_migration_batch()`, `resume_migration()`.
- **`src/migration/prompts.py`** — `build_migration_prompt()` producing taxonomy-driven (system, user) pair with folder/tag/link rules.
- **`src/migration/registry.py`** — `VaultRegistry` read-only taxonomy lookup. `from_active()` class method loads active taxonomy.
- **`src/migration/taxonomy.py`** — `import_taxonomy()` validation and conversion; `validate_taxonomy()` checks folders, tag names, link targets.
- **`src/migration/writer.py`** — `apply_migration()` writes approved notes to target vault; `copy_vault_assets()` copies `.obsidian/` and `Files/`.
- **`src/clawdy/__init__.py`** — Module init.
- **`src/clawdy/git.py`** — Git subprocess wrappers: `pull`, `commit`, `push`, `status`, `is_git_repo`.
- **`src/clawdy/service.py`** — `diff_vaults()`, `create_clawdy_changeset()`, `converge_vaults()`, `ClawdyService` background poller.

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **LLM**: Codex Sonnet 4.6 (default) and Haiku 4.5 via `anthropic` Python SDK (direct SDK, no framework). Batch API for bulk migration.
- **Logging**: `rich` for formatted console output
- **Markdown parsing**: `python-frontmatter` for frontmatter, regex for wikilink extraction
- **Storage**: SQLite with WAL journal mode (`.vault-agent.db`) — changesets, migration jobs, settings, taxonomy proposals
- **Filesystem**: `pathlib.Path.rglob()` for vault traversal, `Path.read_text()` / `.write_text()` for I/O
- **Zotero integration**: `pyzotero` for Zotero API access, background sync with local paper cache
- **UI**: React 19, TypeScript 5.6, Vite 6, Tailwind CSS 4, React Router 7
- **Backend testing**: pytest + pytest-asyncio + httpx + pytest-cov
- **Frontend testing**: vitest + @testing-library/react + MSW (Mock Service Worker)
- **E2E testing**: Playwright (Chromium)
- **CI**: GitHub Actions (`.github/workflows/test.yml`)

## Commands

```bash
uv sync                                            # Install dependencies
uv sync --dev                                      # Install with test dependencies
uv run python -m src.server                        # Start server with hot reload (port 3456)
uv run uvicorn src.server:app --reload --port 3456 # Alternative start command
cd ui && bun install                               # Install UI dependencies
cd ui && bun run dev                               # Start UI dev server (port 5173)
cd ui && bun run build                             # Build UI for production → ui/dist/
```

### Test commands

```bash
uv run pytest tests/ -v                            # Run all backend tests
uv run pytest tests/unit -v                        # Run backend unit tests only
uv run pytest tests/integration -v                 # Run backend integration tests only
uv run pytest tests/ --cov=src --cov-report=term   # Backend tests with coverage
cd ui && bun run test                              # Run frontend tests (vitest)
cd ui && bun run test:watch                        # Frontend tests in watch mode
cd tests/e2e && bunx playwright test               # Run E2E tests (requires ui build)
cd tests/e2e && bunx playwright test --headed      # E2E tests with visible browser
```

## UI

React 19 + TypeScript 5.6 + Vite 6 + Tailwind CSS 4 + React Router 7. Catppuccin Mocha dark theme.

### Router structure

```
/connect           → ConnectVaultPage (vault picker, outside Layout)
/ (Layout wrapper) →
  / (index)        → redirect to /library
  /library         → LibraryPage (Zotero paper browser)
  /library/:key    → AnnotationsPage (paper annotations → processing)
  /changesets      → ChangesetsPage (paginated changeset history)
  /changesets/:id  → ChangesetDetailPage (split-pane review + feedback)
  /migration       → MigrationPage (migration job dashboard)
  /taxonomy        → TaxonomyPage (vault taxonomy: folders/tags/links)
  /clawdy         → ClawdyInboxPage (clawdy inbox: status, changeset list)
  /settings       → SettingsPage (Obsidian-style settings with section sidebar)
* → redirect to /connect
```

### State management

- **`VaultContext`** (`context/VaultContext.tsx`) — global vault connection state (`vaultPath`, `vaultName`, `isLoading`, `setVault`)
- Local React hooks (`useState`, `useCallback`, `useEffect`) — no Redux or external state library
- **`useClickOutside`** (`hooks/useClickOutside.ts`) — click-outside + Escape key detection for popovers/modals

### Pages

- **`ConnectVaultPage`** — First-time vault selection via native file picker; recent vault history
- **`LibraryPage`** — Zotero paper browser with collection sidebar, search, sync status filter, pagination
- **`AnnotationsPage`** — Paper annotations grouped by color; selective toggle; model picker; inline changeset review
- **`ChangesetsPage`** — Paginated changeset history with status filtering and delete
- **`ChangesetDetailPage`** — Split-pane: diff viewer (left) + feedback annotations (right); draggable divider; cost display; regeneration workflow
- **`MigrationPage`** — Renders `MigrationDashboard` component
- **`TaxonomyPage`** — Three-tab taxonomy view (folders/tags/links); hierarchical tag tree; curation modal; vault stats sidebar
- **`ClawdyInboxPage`** — Clawdy status bar; clawdy-filtered changeset list with pagination
- **`SettingsPage`** — Two-panel settings page (section sidebar + settings panel); Clawdy Inbox config (copy vault path, polling toggle, interval)

### Shared components

`Layout`, `Sidebar`, `ChangesetReview`, `DiffViewer`, `MarkdownPreview`, `CollectionTree`, `AnnotationFeedback`, `ChangesetHistory`, `ErrorAlert`, `MigrationDashboard`, `MigrationNoteReview`, `MigrationProgress`, `TaxonomyEditor`, `Skeleton`, `Pagination`, `StatusBadge`, `ZoteroSync`

### Development

- Dev server on port 5173 with proxy to backend at port 3456
- Production build served from `ui/dist/`

## API Endpoints

### Health & Vault Config

- `GET /health` — Health check, returns vault path and status
- `GET /vault/map` — Returns vault structure JSON
- `GET /vault/config` — Current vault path from DB
- `PUT /vault/config` — Set vault path (persists to SettingsStore)
- `POST /vault/picker` — Open native file dialog, return selected path
- `GET /vault/history` — Recent vault paths
- `DELETE /vault/history` — Clear vault history
- `GET /vault/assets/{file_path}` — Serve vault file assets

### Vault Taxonomy

- `GET /vault/taxonomy` — Scan vault and return taxonomy (folders, tags, hierarchy, link targets)
- `POST /vault/taxonomy/apply` — Apply curation operations as a changeset

### Changesets

- `GET /changesets` — List changesets (paginated)
- `GET /changesets/{id}` — Full changeset with ProposedChange details
- `PATCH /changesets/{id}/changes/{change_id}` — Set change status: `"approved"` | `"rejected"`
- `POST /changesets/{id}/apply` — Apply approved changes to disk; optional `{ change_ids: [...] }`
- `POST /changesets/{id}/reject` — Reject entire changeset
- `POST /changesets/{id}/request-changes` — Submit feedback for revision
- `POST /changesets/{id}/regenerate` — Regenerate with feedback context
- `DELETE /changesets/{id}` — Delete changeset

### Zotero

- `POST /zotero/sync` — Batch sync papers from Zotero
- `GET /zotero/collections` — List Zotero collections
- `GET /zotero/papers?collection_key=...&offset=0&limit=25&search=...&sync_status=...` — Paginated paper list
- `GET /zotero/papers/cache-status` — Cache stats and sync status
- `POST /zotero/papers/refresh` — Trigger background cache sync
- `GET /zotero/papers/{paper_key}/annotations` — All annotations for a paper
- `GET /zotero/papers/{paper_key}/batch-status` — Batch job status for paper
- `POST /zotero/papers/{paper_key}/sync` — Sync single paper; optional `{ excluded_annotation_keys: [...] }`
- `GET /zotero/status` — Zotero configuration status

### Migration

- `POST /migration/estimate` — Estimate token cost for full vault migration
- `POST /migration/taxonomy/import` — Import and validate taxonomy proposal
- `GET /migration/taxonomy/{id}` — Get taxonomy proposal
- `PUT /migration/taxonomy/{id}` — Update taxonomy (curate folders/tags/links)
- `POST /migration/taxonomy/{id}/activate` — Set taxonomy as active (deactivates others)
- `GET /migration/jobs` — List migration jobs
- `POST /migration/jobs` — Create migration job (scans vault, creates notes)
- `GET /migration/jobs/{id}` — Get job details
- `GET /migration/jobs/{id}/notes` — Paginated list of migration notes
- `PATCH /migration/jobs/{id}/notes/{note_id}` — Update note status/content
- `POST /migration/jobs/{id}/notes/{note_id}/retry` — Retry failed note
- `POST /migration/jobs/{id}/apply` — Write approved notes to target vault
- `POST /migration/jobs/{id}/cancel` — Cancel running job
- `POST /migration/jobs/{id}/resume` — Resume failed job (resets stuck notes)
- `GET /migration/registry` — Get active taxonomy via VaultRegistry

### Clawdy Inbox

- `GET /clawdy/config` — Current clawdy config (copy vault path, interval, enabled)
- `PUT /clawdy/config` — Update clawdy config
- `GET /clawdy/status` — Clawdy service status (last poll, last error, pending count)
- `POST /clawdy/trigger` — Trigger immediate poll
- `POST /clawdy/converge/{changeset_id}` — Sync rejected changes back to copy vault, commit and push

### Changeset lifecycle

- Changesets persisted in SQLite; no automatic expiry
- Changeset status: `pending` → `applied` | `rejected` | `partially_applied` | `skipped`
- Individual change status: `pending` → `approved` | `rejected` | `applied`

### Migration job lifecycle

- Job status: `pending` → `migrating` → `review` → `applying` → `completed` | `failed` | `cancelled`
- Note status: `pending` → `processing` → `proposed` | `approved` (NO_CHANGES_NEEDED) | `failed` → `applied` | `rejected` | `skipped`
- Taxonomy status: `imported` → `curated` → `active`

## Environment Setup

Required in `.env` (loaded via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...       # Required
PORT=3456                          # Optional — default 3456
DB_PATH=.vault-agent.db            # Optional — default ".vault-agent.db"
ZOTERO_API_KEY=...                 # Optional — Zotero integration
ZOTERO_LIBRARY_ID=...              # Optional — Zotero library ID
ZOTERO_LIBRARY_TYPE=user           # Optional — default "user"
```

`VAULT_PATH` is **not** an env var. It is set via the UI file picker and persisted in SQLite (`SettingsStore`). On first launch the app shows `ConnectVaultPage`.

## Key Design Decisions

### Additive-only writes
Two write operations: create note and append section. No modifications to existing prose, no deletions, no moves, no renames. Worst case is an unwanted new note or a bad append, both trivially reverted with `git checkout`. Migration writes go to a separate target vault directory.

### Clawdy write policy
`replace_note` and `delete_note` operations are available but scoped exclusively to `source_type="clawdy"` changesets. These are needed because OpenClaw may modify or remove files in the copy vault, and convergence must mirror those operations.

### Direct Anthropic SDK
No LangChain/LlamaIndex. Single-call synthesis for Zotero, per-note migration calls with prompt caching. The SDK is used directly for both streaming and batch API.

### Changeset approval workflow
Content is previewed before being written. All LLM output is wrapped in a `Changeset` with diffs and persisted to SQLite without touching the vault. The client approves or rejects individual changes, then calls apply. This pattern is shared across Zotero sync, taxonomy curation, and migration.

### Dynamic vault config
Vault path is stored in `SettingsStore` (SQLite key-value), not an env var. Users select via native file picker in the UI. History of recent vaults is maintained. Config is loaded into `app.state` at startup and updated in-place on change.

### Migration system
Job-based: one `MigrationJob` contains one `MigrationNote` per vault file. Each note is independently processed by Codex with a taxonomy-driven system prompt. Two execution modes: concurrent async (semaphore=5) or Anthropic Batch API (50% cost). System prompt is cached across notes via ephemeral cache control. Notes returning `NO_CHANGES_NEEDED` are auto-approved. Target vault is a separate directory; source vault is never modified.

### Taxonomy lifecycle
`imported` → `curated` → `active`. Only one taxonomy can be active at a time. Activating a taxonomy deactivates all others. The active taxonomy drives migration prompts (folder assignments, tag hierarchy, link targets).

### Prompt caching
Migration system prompt (taxonomy + rules) uses Anthropic's ephemeral cache control. First call pays cache_write cost; subsequent calls hit cache_read (90% cheaper). This is critical for vault-wide migration where hundreds of notes share the same system prompt.

## Code Conventions

### Comment docstrings

All Python functions and classes use `#` comment blocks above the definition — **not** triple-quote docstrings. This is a strict project convention; every new or modified function must follow it.

```python
# One-line summary of what the function does.
#
# Optional expanded description if needed.
#
# Args:
#     param_name: What it represents.
#     other_param: What it represents.
#
# Returns:
#     What the function returns.
#
# Raises:
#     ExceptionType: When this happens.
def function_name(param_name: str, other_param: int) -> str:
```

Rules:
- **Always `#` comments**, never triple-quote docstrings
- Blank `#` line between sections (summary, Args, Returns, Raises)
- 4-space indent for content under section headers
- Public functions + anything with 2+ params: full structure (summary, Args, Returns)
- Trivial private helpers: one-liner `#` comment only
- FastAPI route handlers: one-liner `#` comment above the decorator
- Classes: brief `#` comment above the `class` line
- Methods: same format, indented to match the method
- Omit Raises section unless the function actually raises
- Omit Returns section for `-> None` functions
- Reference examples: `src/vault/reader.py`, `src/db/changesets.py`

### Frontend conventions

- **Pages**: `*Page` suffix, in `ui/src/pages/`. One per route.
- **Hooks**: `use*` prefix, in `ui/src/hooks/`.
- **Context**: `ui/src/context/`. `VaultContext` is the only global context.
- **Components**: `ui/src/components/`. Reusable UI shared across pages.
- **State**: React Context + local hooks. No Redux or external state library.

### DB store pattern

All stores are lazy singletons via `get_*_store()` in `src/db/__init__.py`. Tests reset the global to inject `:memory:` SQLite. Stores use WAL journal mode and store complex data as JSON columns.

## Obsidian Conventions

- **Frontmatter**: YAML block with `---`. Always use `tags` (plural array), never `tag`.
- **Wikilinks**: `[[Note Title]]`, `[[Note Title|display]]`, `[[Note Title#Heading]]`
- **Tags**: `#tag` inline or `tags: [tag1, tag2]` in frontmatter. Hierarchical: `#projects/vault-agent`
- **Callouts**: `> [!note]`, `> [!warning]` — never modify or break these
- **Dataview queries**: Treat as opaque, never modify
- **Embeds**: `![[Note Title]]` — different from a regular wikilink
- **Block references**: `^block-id` — never modify or remove

### New note template

```markdown
---
tags: []
source: ""
created: YYYY-MM-DD
---

# Note Title

Content here with [[wikilinks]] to related notes.

## Source Highlights

> Highlighted text from source

Commentary about the highlight.
```

## Testing

### Testability design

- **Lazy store singletons** (`src/db/`): `get_changeset_store()` / `get_batch_job_store()` / `get_migration_store()` / `get_settings_store()` in `src/db/__init__.py`. Tests reset the global to inject `:memory:` SQLite.
- **Deferred config** (`src/server.py`): `load_config()` runs inside `lifespan()`, stored on `app.state`. Route handlers access config via `request.app.state.config`. Tests set `app.state.config` directly.

### Backend tests (pytest)

Config in `pyproject.toml` under `[tool.pytest.ini_options]`.

**Root fixtures** (`tests/conftest.py`):
- `tmp_vault` — temp dir with sample `.md` notes and `.obsidian/` marker
- `app_config` — `AppConfig` with fake API keys pointing at `tmp_vault`

**Factories** (`tests/factories.py`): `make_content_item()`, `make_zotero_content_item()`, `make_proposed_change()`, `make_routing_info()`, `make_changeset()` — all accept `**overrides`.

**Unit tests** (`tests/unit/`): Pure functions, no mocks. Covers vault reader/writer, diff, prompts, models, agent cost, zotero parsing, taxonomy, migration writer.

**Integration tests** (`tests/integration/`): Uses `:memory:` SQLite stores, `tmp_path` filesystem, and `httpx.AsyncClient` with `ASGITransport` for server route tests.

### Frontend tests (vitest)

Config in `ui/vitest.config.ts` (jsdom environment).

**MSW setup** (`ui/src/__tests__/setup.ts`, `handlers.ts`): Mock Service Worker intercepts all API fetch calls. Tests override specific handlers via `server.use()`.

**Factories** (`ui/src/__tests__/factories.ts`): `makeContentItem()`, `makeProposedChange()`, `makeChangeset()`, `makeChangesetSummary()`, `makePaper()`, `makeAnnotation()`, `makePassageAnnotation()`, `makeCollection()`, `makeTagInfo()`, `makeLinkTargetInfo()`, `makeVaultTaxonomy()`.

**Test files**: Component tests (`ErrorAlert`, `CollectionTree`, `DiffViewer`, `AnnotationFeedback`, `ChangesetHistory`, `ChangesetReview`, `TaxonomyPage`), utility tests (`obsidian`, `diff`), API client tests.

### E2E tests (Playwright)

Config in `tests/e2e/playwright.config.ts`. Uses `page.route()` for API mocking (no real backend). Serves built UI via `vite preview`.

**Specs**: `health.spec.ts`, `history.spec.ts`, `papers.spec.ts`, `sync-flow.spec.ts`.

**Prerequisite**: `cd ui && bun run build` before running E2E tests.

### CI pipeline

`.github/workflows/test.yml` runs on push/PR to `main`:
- **backend** job: `uv sync --dev` → `pytest` with coverage
- **frontend** job: `bun install` → `vitest`
- **e2e** job (depends on frontend): build UI → install Playwright → run specs

## Explicit Boundaries

- Never use triple-quote docstrings (`#` comments only)
- Never destructively edit existing vault notes (additive-only writes; migration writes to separate target vault)
- Never modify dataview queries, block references, or callouts
- Never use LangChain/LlamaIndex (direct Anthropic SDK only)
- Never store vault_path in .env (it's DB-backed via SettingsStore)
- Never use `tag` (singular) in frontmatter — always `tags` (plural array)

## File Structure

```
vault-agent/
├── AGENTS.md
├── README.md
├── .env                   # gitignored
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── server.py
│   ├── config.py
│   ├── logging_config.py      # Rich-based logging setup
│   ├── db/
│   │   ├── __init__.py        # Re-exports, lazy singletons, getters
│   │   ├── changesets.py      # ChangesetStore
│   │   ├── batch_jobs.py      # BatchJobStore
│   │   ├── migration.py       # MigrationStore (jobs, notes, taxonomies)
│   │   └── settings.py        # SettingsStore (key-value config)
│   ├── models/
│   │   ├── __init__.py        # Re-exports all models
│   │   ├── content.py         # ContentItem, SourceMetadata, SourceType
│   │   ├── changesets.py      # Changeset, ProposedChange, RoutingInfo, TokenUsage
│   │   ├── vault.py           # VaultNote, VaultMap, VaultTaxonomy, VaultConfig models
│   │   ├── migration.py       # TagNode, LinkTarget, TaxonomyProposal, MigrationJob/Note, CostEstimate
│   │   ├── tools.py           # CreateNoteInput, UpdateNoteInput
│   │   └── zotero.py          # Zotero request/response models
│   ├── vault/
│   │   ├── __init__.py        # validate_path(), iter_markdown_files()
│   │   ├── reader.py
│   │   ├── writer.py
│   │   └── taxonomy.py        # build_vault_taxonomy(), apply_taxonomy_curation()
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   ├── utils.py           # Model pricing, compute_cost(), create_with_retry()
│   │   ├── changeset.py       # Applies approved changes to vault
│   │   ├── diff.py            # Unified diff generation
│   │   └── wikify.py          # Post-processing wikilink auto-linker
│   ├── zotero/
│   │   ├── __init__.py
│   │   ├── client.py          # Zotero API client (pyzotero)
│   │   ├── sync.py            # Annotation → ContentItem conversion
│   │   ├── orchestrator.py    # Sync coordination
│   │   └── background.py      # Background cache refresh
│   ├── migration/
│   │   ├── __init__.py
│   │   ├── migrator.py        # Migration engine: estimate, run, batch, resume
│   │   ├── prompts.py         # Taxonomy-driven LLM prompt builder
│   │   ├── registry.py        # VaultRegistry: read-only taxonomy lookup
│   │   ├── taxonomy.py        # import_taxonomy(), validate_taxonomy()
│   │   └── writer.py          # apply_migration(), copy_vault_assets()
│   └── clawdy/
│       ├── __init__.py
│       ├── git.py             # Git subprocess wrappers
│       └── service.py         # Vault diffing, changeset creation, convergence, poll service
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Root fixtures: tmp_vault, app_config
│   ├── factories.py           # Test data builders
│   ├── unit/
│   │   ├── test_vault_reader.py
│   │   ├── test_vault_writer.py
│   │   ├── test_vault_init.py
│   │   ├── test_diff.py
│   │   ├── test_prompts.py
│   │   ├── test_models.py
│   │   ├── test_agent_cost.py
│   │   ├── test_zotero_parsing.py
│   │   ├── test_taxonomy.py
│   │   ├── test_migration_writer.py
│   │   ├── test_clawdy_git.py
│   │   └── test_clawdy_service.py
│   ├── integration/
│   │   ├── conftest.py        # :memory: store fixtures
│   │   ├── test_store.py
│   │   ├── test_vault_io.py
│   │   ├── test_changeset_apply.py
│   │   ├── test_vault_map.py
│   │   ├── test_server_routes.py
│   │   ├── test_clawdy_apply.py
│   │   └── test_clawdy_routes.py
│   └── e2e/
│       ├── package.json       # Playwright dependency
│       ├── playwright.config.ts
│       ├── mock-api.ts        # Route interception helpers
│       └── specs/
│           ├── health.spec.ts
│           ├── history.spec.ts
│           ├── papers.spec.ts
│           └── sync-flow.spec.ts
├── ui/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts       # Test config (jsdom, MSW setup)
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx           # Entry point (StrictMode + CSS imports)
│       ├── App.tsx            # VaultProvider + RouterProvider
│       ├── router.tsx         # React Router 7 route definitions
│       ├── types.ts           # TypeScript type definitions
│       ├── styles.css         # Catppuccin Mocha theme, Obsidian styles
│       ├── utils.ts           # formatError utility
│       ├── api/
│       │   └── client.ts      # API client (fetch wrapper)
│       ├── context/
│       │   └── VaultContext.tsx # Global vault state
│       ├── hooks/
│       │   └── useClickOutside.ts
│       ├── pages/
│       │   ├── ConnectVaultPage.tsx
│       │   ├── LibraryPage.tsx
│       │   ├── AnnotationsPage.tsx
│       │   ├── ChangesetsPage.tsx
│       │   ├── ChangesetDetailPage.tsx
│       │   ├── MigrationPage.tsx
│       │   ├── TaxonomyPage.tsx
│       │   ├── ClawdyInboxPage.tsx
│       │   └── SettingsPage.tsx
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── Sidebar.tsx
│       │   ├── ZoteroSync.tsx
│       │   ├── ChangesetReview.tsx
│       │   ├── ChangesetHistory.tsx
│       │   ├── DiffViewer.tsx
│       │   ├── MarkdownPreview.tsx
│       │   ├── CollectionTree.tsx
│       │   ├── AnnotationFeedback.tsx
│       │   ├── MigrationDashboard.tsx
│       │   ├── MigrationNoteReview.tsx
│       │   ├── MigrationProgress.tsx
│       │   ├── TaxonomyEditor.tsx
│       │   ├── ErrorAlert.tsx
│       │   ├── Skeleton.tsx
│       │   ├── Pagination.tsx
│       │   └── StatusBadge.tsx
│       ├── utils/
│       │   ├── obsidian.ts    # Wikilink/tag/embed preprocessing
│       │   └── diff.ts        # Diff computation (extracted from DiffViewer)
│       └── __tests__/
│           ├── setup.ts       # MSW server lifecycle
│           ├── handlers.ts    # MSW request handlers
│           ├── factories.ts   # TS test data builders
│           ├── utils/
│           │   ├── obsidian.test.ts
│           │   └── diff.test.ts
│           ├── components/
│           │   ├── ErrorAlert.test.tsx
│           │   ├── CollectionTree.test.tsx
│           │   ├── DiffViewer.test.tsx
│           │   ├── AnnotationFeedback.test.tsx
│           │   ├── ChangesetHistory.test.tsx
│           │   ├── ChangesetReview.test.tsx
│           │   └── TaxonomyPage.test.tsx
│           └── api/
│               └── client.test.ts
├── .github/
│   └── workflows/
│       ├── Codex.yml
│       ├── Codex-review.yml
│       └── test.yml           # CI: backend + frontend + e2e
├── test-highlights/
│   └── highlights.json
└── .Codex/
    └── skills/
        └── update-doc/        # Doc update skill
```
