# CLAUDE.md — Vault Agent

## Project Overview

A **FastAPI backend server** running on Python that takes Zotero annotations and synthesizes them into Obsidian vault notes using Claude as the AI reasoning layer. Annotations are submitted via HTTP API (through Zotero sync), synthesized by a single Claude LLM call into a paper note, and written to the filesystem as Obsidian-compatible markdown after user approval.

## Architecture

```
Zotero Sync Flow:
  POST /zotero/papers/{paper_key}/sync (or POST /zotero/sync for batch)
    → Fetch annotations from Zotero API
    → Build ContentItem list from annotations
    → Single Claude LLM call synthesizes annotations into a paper note
    → Proposed note wrapped in a Changeset with diff (persisted in SQLite)
    → Response: full Changeset with diff and routing info

  Apply (POST /changesets/{id}/apply):
    → Client approves/rejects individual changes
    → Approved changes written to vault filesystem
```

### Key Modules

- **`src/server.py`** — FastAPI entry point. Route definitions, middleware, request validation.
- **`src/models/`** — Pydantic models package (`ContentItem`, `Changeset`, `VaultNote`, `VaultMap`, Zotero types, etc.). Split into `content.py`, `changesets.py`, `vault.py`, `tools.py`, `search.py`, `zotero.py`.
- **`src/config.py`** — Loads env vars, validates VAULT_PATH, API keys, and optional Zotero config.
- **`src/vault/reader.py`** — Scans the Obsidian vault filesystem. Parses frontmatter, extracts wikilinks, builds the vault map string for the LLM context.
- **`src/vault/writer.py`** — Filesystem write operations: create note, append to note. All operations are additive-only (no destructive edits).
- **`src/agent/agent.py`** — Single-call Zotero note synthesis (`generate_zotero_note`), batch API support, retry logic, cost tracking.
- **`src/agent/prompts.py`** — Zotero synthesis prompt builder. Produces (system, user) message pair from annotations and metadata, with optional feedback for regeneration.
- **`src/db/`** — SQLite-backed persistent stores package (WAL journal mode). `changesets.py` (`ChangesetStore`), `batch_jobs.py` (`BatchJobStore`), `migration.py` (`MigrationStore`). Lazy singletons in `__init__.py`. Stores data in `.vault-agent.db`.
- **`src/agent/changeset.py`** — `apply_changeset(vault_path, changeset, approved_ids?)`. Iterates approved `ProposedChange` objects and dispatches to `create_note` / `update_note`.
- **`src/agent/diff.py`** — `generate_diff(path, original, proposed)`. Wraps `difflib.unified_diff` to produce unified diffs for display in the UI.
- **`src/vault/__init__.py`** — Path validation utility (`validate_path`) preventing traversal outside vault root.
- **`src/zotero/client.py`** — Zotero API client wrapping `pyzotero`. Fetches papers, annotations, collections.
- **`src/zotero/sync.py`** — Zotero highlight sync logic. Converts annotations to `ContentItem` list and runs agent.
- **`src/zotero/orchestrator.py`** — Coordination layer for Zotero sync operations.
- **`src/zotero/background.py`** — Background sync tasks for paper cache refresh.

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **LLM**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) via `anthropic` Python SDK (direct SDK, no framework)
- **Markdown parsing**: `python-frontmatter` for frontmatter, regex for wikilink extraction
- **Changeset storage**: SQLite with WAL journal mode (`.vault-agent.db`)
- **Filesystem**: `pathlib.Path.rglob()` for vault traversal, `Path.read_text()` / `.write_text()` for I/O
- **Zotero integration**: `pyzotero` for Zotero API access, background sync with local paper cache
- **UI**: React 19, TypeScript 5.6, Vite 6, Tailwind CSS 4
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

A React 19 + TypeScript single-page application built with Vite 6 and Tailwind CSS 4. Catppuccin Mocha dark theme.

### Workflow (3 steps)
1. **Papers** — Browse Zotero papers with collection sidebar, search, sync status filter, pagination. Trigger cache refresh from Zotero API.
2. **Annotations** — View annotations for a selected paper, grouped by color. Toggle individual annotations on/off before processing.
3. **Processing** — Agent runs, produces a changeset. Review proposed changes via `ChangesetReview` component with diff/preview toggle, approve/reject individual changes, apply to vault.

### Components
- **`Layout`** — App shell with header
- **`ZoteroSync`** — Main workflow component (papers → annotations → processing)
- **`ChangesetReview`** — Changeset review UI with approve/reject/apply actions
- **`DiffViewer`** — Structured diff display with line numbers, collapsible context sections
- **`MarkdownPreview`** — Obsidian-aware markdown renderer (wikilinks, embeds, tags, callouts)
- **`CollectionTree`** — Hierarchical Zotero collection browser with expand/collapse
- **`ErrorAlert`** — Error display component

### Features
- Obsidian-aware markdown rendering (wikilinks, embeds, tags, callouts)
- Structured diff viewer with line numbers and collapsible sections
- Dual view modes: diff and markdown preview for each proposed change

### Development
- Dev server on port 5173 with proxy to backend at port 3456
- Production build served from `ui/dist/`

## API Endpoints

### Health & Vault
- `GET /health` — Health check, returns vault path and status
- `GET /vault/map` — Returns vault structure JSON (for debugging)

### Changesets
- `GET /changesets/{id}` — Get full changeset with all ProposedChange details
- `PATCH /changesets/{id}/changes/{change_id}` — Set individual change status to `"approved"` | `"rejected"`
- `POST /changesets/{id}/apply` — Apply approved changes to disk; optional body: `{ change_ids: [...] }`
- `POST /changesets/{id}/reject` — Reject entire changeset and all its changes

### Zotero
- `POST /zotero/sync` — Sync papers from Zotero, process annotations, create changesets
- `GET /zotero/collections` — List Zotero collections (cached or live)
- `GET /zotero/papers/cache-status` — Cached paper count, last updated, sync in progress
- `POST /zotero/papers/refresh` — Trigger background paper cache sync from Zotero
- `GET /zotero/papers?collection_key=...&offset=0&limit=25&search=...&sync_status=...` — Paginated paper list with sync status
- `GET /zotero/papers/{paper_key}/annotations` — All annotations for a paper
- `POST /zotero/papers/{paper_key}/sync` — Sync single paper; optional body: `{ excluded_annotation_keys: [...] }`
- `GET /zotero/status` — Zotero configuration status (configured, last_version, last_synced)

### Changeset lifecycle

- Changesets are persisted in SQLite; no automatic expiry
- Changeset status: `pending` → `applied` | `rejected` | `partially_applied` | `skipped`
- Individual change status: `pending` → `approved` | `rejected` | `applied`

### ContentItem payload format

```json
{
  "text": "The highlighted text",
  "source": "URL or document title",
  "annotation": "Optional user note",
  "source_type": "web" | "zotero" | "book",
  "source_metadata": {
    "title": "Paper title",
    "doi": "10.1234/...",
    "authors": ["Author One"],
    "year": "2024",
    "paper_key": "ZOTERO_KEY"
  }
}
```

## Environment Setup

Required in `.env` (loaded via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
VAULT_PATH=/absolute/path/to/obsidian/vault
PORT=3456
DB_PATH=.vault-agent.db           # Optional — default ".vault-agent.db"
ZOTERO_API_KEY=...             # Optional — Zotero integration
ZOTERO_LIBRARY_ID=...          # Optional — Zotero library ID
ZOTERO_LIBRARY_TYPE=user       # Optional — default "user"
```

`VAULT_PATH` must point to the root of the Obsidian vault (the directory containing `.obsidian/`).
`ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` are required for Zotero integration endpoints.

## Key Design Decisions

### Additive-only writes
Two write operations: create note and append section. No modifications to existing prose, no deletions, no moves, no renames. Worst case is an unwanted new note or a bad append, both trivially reverted with `git checkout`.

### Direct Anthropic SDK
Single-call synthesis in ~40 lines. No LangChain/LlamaIndex — a framework adds complexity without value for this use case.

### Changeset approval workflow
Content is previewed before being written. The synthesis call produces a proposed note, which is wrapped in a `Changeset` with a diff and persisted to SQLite without touching the vault. The client approves or rejects individual changes, then calls `POST /changesets/{id}/apply` to write only approved changes. Git remains useful for reviewing what landed, but the primary safety mechanism is the approval gate.

### Zotero integration
Papers and annotations are fetched via `pyzotero`. A local paper cache supports paginated browsing, search, and collection filtering. Background sync refreshes the cache from Zotero API. Per-paper sync creates a changeset by converting annotations to `ContentItem` objects and running the agent. Annotations can be excluded before sync.

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

Two refactors enable test imports without side effects:
- **Lazy store singletons** (`src/db/`): `get_changeset_store()` / `get_batch_job_store()` / `get_migration_store()` in `src/db/__init__.py`. Tests reset the global to inject `:memory:` SQLite.
- **Deferred config** (`src/server.py`): `load_config()` runs inside `lifespan()`, stored on `app.state`. Route handlers access config via `request.app.state.config`. Tests set `app.state.config` directly.

### Backend tests (pytest)

126 tests in `tests/`. Config in `pyproject.toml` under `[tool.pytest.ini_options]`.

**Root fixtures** (`tests/conftest.py`):
- `tmp_vault` — temp dir with sample `.md` notes and `.obsidian/` marker
- `app_config` — `AppConfig` with fake API keys pointing at `tmp_vault`

**Factories** (`tests/factories.py`): `make_content_item()`, `make_zotero_content_item()`, `make_proposed_change()`, `make_routing_info()`, `make_changeset()` — all accept `**overrides`.

**Unit tests** (`tests/unit/`): Pure functions, no mocks. Covers vault reader/writer, diff, prompts, models, agent cost, zotero parsing.

**Integration tests** (`tests/integration/`): Uses `:memory:` SQLite stores (via `tests/integration/conftest.py`), `tmp_path` filesystem, and `httpx.AsyncClient` with `ASGITransport` for server route tests. Covers store CRUD, vault I/O, changeset apply, vault map, server routes.

### Frontend tests (vitest)

46 tests in `ui/src/__tests__/`. Config in `ui/vitest.config.ts` (jsdom environment).

**MSW setup** (`ui/src/__tests__/setup.ts`, `handlers.ts`): Mock Service Worker intercepts all API fetch calls with canned responses. Tests override specific handlers via `server.use()` for error/edge cases.

**Factories** (`ui/src/__tests__/factories.ts`): `makeContentItem()`, `makeProposedChange()`, `makeChangeset()`, `makePaper()`, `makeAnnotation()`, `makeCollection()`.

**Test files**: `utils/obsidian.test.ts`, `utils/diff.test.ts`, `components/ErrorAlert.test.tsx`, `components/CollectionTree.test.tsx`, `components/DiffViewer.test.tsx`, `api/client.test.ts`.

**Extracted module**: `ui/src/utils/diff.ts` — `computeLines()` and `groupLines()` extracted from `DiffViewer.tsx` for direct unit testing.

### E2E tests (Playwright)

19 tests in `tests/e2e/specs/`. Config in `tests/e2e/playwright.config.ts`.

Uses Playwright's `page.route()` for API mocking (no real backend needed). Serves the built UI via `vite preview`. Mock data defined in `tests/e2e/mock-api.ts`.

**Specs**: `health.spec.ts` (page load, header, Zotero config), `history.spec.ts` (changeset history), `papers.spec.ts` (paper list, search, filters, sidebar), `sync-flow.spec.ts` (full paper → annotations → process → review flow).

**Prerequisite**: `cd ui && bun run build` before running E2E tests.

### CI pipeline

`.github/workflows/test.yml` runs on push/PR to `main`:
- **backend** job: `uv sync --dev` → `pytest` with coverage
- **frontend** job: `bun install` → `vitest`
- **e2e** job (depends on frontend): build UI → install Playwright → run specs

## File Structure

```
vault-agent/
├── CLAUDE.md
├── README.md
├── .env                   # gitignored
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── src/
│   ├── __init__.py
│   ├── server.py
│   ├── config.py
│   ├── db/
│   │   ├── __init__.py        # Re-exports, lazy singletons, getters
│   │   ├── changesets.py      # ChangesetStore
│   │   ├── batch_jobs.py      # BatchJobStore
│   │   └── migration.py       # MigrationStore
│   ├── models/
│   │   ├── __init__.py        # Re-exports all models
│   │   ├── content.py         # ContentItem, SourceMetadata, SourceType
│   │   ├── changesets.py      # Changeset, ProposedChange, RoutingInfo
│   │   ├── vault.py           # VaultNote, VaultMap, VaultNoteSummary
│   │   ├── tools.py           # ReadNoteInput, CreateNoteInput, UpdateNoteInput
│   │   └── zotero.py          # Zotero request/response models
│   ├── vault/
│   │   ├── __init__.py        # validate_path()
│   │   ├── reader.py
│   │   └── writer.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   ├── changeset.py       # Applies approved changes to vault
│   │   ├── diff.py            # Unified diff generation
│   │   └── wikify.py          # Post-processing wikilink auto-linker
│   └── zotero/
│       ├── __init__.py
│       ├── client.py          # Zotero API client (pyzotero)
│       ├── sync.py            # Annotation → ContentItem conversion
│       ├── orchestrator.py    # Sync coordination
│       └── background.py     # Background cache refresh
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
│   │   └── test_zotero_parsing.py
│   ├── integration/
│   │   ├── conftest.py        # :memory: store fixtures
│   │   ├── test_store.py
│   │   ├── test_vault_io.py
│   │   ├── test_changeset_apply.py
│   │   ├── test_vault_map.py
│   │   └── test_server_routes.py
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
│       ├── main.tsx           # Entry point
│       ├── App.tsx            # Root component (renders Layout + ZoteroSync)
│       ├── types.ts           # TypeScript type definitions
│       ├── styles.css         # Catppuccin Mocha theme, Obsidian styles
│       ├── utils.ts           # formatError utility
│       ├── api/
│       │   └── client.ts      # API client (fetch wrapper)
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── ZoteroSync.tsx
│       │   ├── ChangesetReview.tsx
│       │   ├── DiffViewer.tsx
│       │   ├── MarkdownPreview.tsx
│       │   ├── CollectionTree.tsx
│       │   ├── AnnotationFeedback.tsx
│       │   ├── ChangesetHistory.tsx
│       │   └── ErrorAlert.tsx
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
│           │   └── ChangesetHistory.test.tsx
│           └── api/
│               └── client.test.ts
├── .github/
│   └── workflows/
│       ├── claude.yml
│       ├── claude-code-review.yml
│       └── test.yml           # CI: backend + frontend + e2e
├── test-highlights/
│   └── highlights.json
└── .claude/
    └── skills/
        └── update-doc/        # Doc update skill
```
