---
name: update-doc
description: Scan the codebase and update README.md and CLAUDE.md to reflect the current implementation.
disable-model-invocation: true
---

# Update Documentation

Scan the entire codebase and update `README.md` and `CLAUDE.md` to accurately reflect the current state of the project.

## Workflow

### Step 0: Check What Changed (optional shortcut)

Run `git log --oneline --all -- CLAUDE.md README.md` to find the last doc-touching commit. Then run `git diff <that-commit>..HEAD --name-only` to get a list of files changed since then.

- If the diff is small (≤10 files), focus the scan in Steps 1–3 on only those areas — skip reading unchanged modules.
- If the diff is large or the last doc commit is very old, fall back to a full scan.
- If no prior doc commit exists, do a full scan.

### Step 1: Scan Backend

Read all backend source files in `src/`:

**Core:**
- `src/server.py` — Extract all API endpoints (routes, methods, request/response models)
- `src/config.py` — Extract environment variables and configuration
- `src/store.py` — Extract storage schema and operations

**Models (`src/models/`):**
- `src/models/__init__.py` — Re-exports
- `src/models/content.py` — Content/highlight models
- `src/models/changesets.py` — Changeset and ProposedChange models
- `src/models/vault.py` — Vault-related models (VaultNote, VaultMap, etc.)
- `src/models/tools.py` — Tool input/output models
- `src/models/search.py` — Search result models
- `src/models/zotero.py` — Zotero integration models

**Agent (`src/agent/`):**
- `src/agent/agent.py` — Agent loop structure and LLM config
- `src/agent/tools.py` — Tool definitions, inputs, outputs, constraints
- `src/agent/prompts.py` — System prompt structure
- `src/agent/changeset.py` — Changeset application logic
- `src/agent/diff.py` — Diff generation logic

**Vault (`src/vault/`):**
- `src/vault/__init__.py` — Path validation (`validate_path`)
- `src/vault/reader.py` — Vault reading logic
- `src/vault/writer.py` — Write operations

**RAG (`src/rag/`):**
- `src/rag/*.py` — RAG pipeline: chunker, embedder, store, indexer, search

**Zotero (`src/zotero/`):**
- `src/zotero/client.py` — Zotero API wrapper
- `src/zotero/sync.py` — SQLite-backed sync state tracking
- `src/zotero/background.py` — Async background syncer
- `src/zotero/orchestrator.py` — Agent pipeline bridge for Zotero items

**Catch-all:** Glob `src/**/*.py` and read any files not listed above. New modules may have been added since this skill was last updated.

### Step 2: Scan Frontend

Read all files in `ui/src/`:
- `ui/src/App.tsx` — Routes and views
- `ui/src/types.ts` — TypeScript type definitions
- `ui/src/api/client.ts` — API client functions
- `ui/src/hooks/useChangesets.ts` — Custom hooks
- `ui/src/utils.ts`, `ui/src/utils/obsidian.ts` — Utility modules
- `ui/src/components/ChangesetHistory.tsx` — Changeset history view
- `ui/src/components/ChangesetReview.tsx` — Changeset review/approval UI
- `ui/src/components/CollectionTree.tsx` — Zotero collection tree browser
- `ui/src/components/ContentForm.tsx` — Content submission form
- `ui/src/components/ContentPreview.tsx` — Content preview display
- `ui/src/components/DiffViewer.tsx` — Unified diff viewer
- `ui/src/components/ErrorAlert.tsx` — Error display component
- `ui/src/components/Layout.tsx` — App layout/shell
- `ui/src/components/MarkdownPreview.tsx` — Obsidian-aware markdown renderer
- `ui/src/components/StatusBadge.tsx` — Status indicator badges
- `ui/src/components/VaultSearch.tsx` — Vault semantic search UI
- `ui/src/components/ZoteroSync.tsx` — Zotero sync management UI
- `ui/package.json` — Dependencies and scripts

**Catch-all:** Glob `ui/src/**/*.{tsx,ts}` and read any files not listed above.

### Step 3: Scan Config

- `pyproject.toml` — Python dependencies, scripts, project metadata
- `.env.example` — Required/optional environment variables (includes `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`)
- `ui/package.json` — Frontend dependencies and scripts
- `ui/vite.config.ts` — Build and dev server config
- `ui/tsconfig.json` — TypeScript config

### Step 4: Read Current Docs

Read `README.md` and `CLAUDE.md` in full. Note their current structure and content.

### Step 5: Update CLAUDE.md

Update every section to match the actual implementation. Key sections to verify and update:

- **Project Overview** — High-level description
- **Architecture** — Request flow diagram, module interactions
- **Key Modules** — Every module with accurate one-line descriptions
- **Tech Stack** — All dependencies with correct versions/names
- **Commands** — All build/run/dev commands
- **UI** — Views, features, components, development setup
- **API Endpoints** — Must exactly match routes in `server.py`
- **Environment Setup** — Must match `.env.example`
- **Key Design Decisions** — Update if architecture has changed
- **Obsidian Conventions** — Update if conventions have changed
- **Agent Tool Definitions** — Must exactly match schemas in `tools.py`
- **File Structure** — Must reflect actual files on disk (use glob to verify)

### Step 6: Update README.md

Update user-facing documentation:

- **Overview** — What the project does
- **Tech stack summary** — Key technologies
- **Prerequisites** — Required tools and versions
- **Setup instructions** — Installation and configuration steps
- **Usage** — How to run the project

### Step 7: Verify

Re-read both `README.md` and `CLAUDE.md` after editing. Confirm:
- No broken markdown formatting
- No stale references to removed features
- No missing references to new features
- File structure tree matches actual disk layout
- API endpoints match actual routes
- Tool definitions match actual schemas

## Rules

- **Preserve existing structure and style** — Don't reorganize sections unnecessarily
- **Don't remove sections** — Update them or add new ones
- **Keep README.md user-focused** — Setup, overview, quick start
- **Keep CLAUDE.md developer-focused** — Full technical reference
- **Be accurate** — Every endpoint, model, tool, and file path must match the code
- **Be concise** — Don't add verbose prose; match the existing terse style

## Arguments

No arguments. Scans the full codebase every time (or uses Step 0 shortcut for incremental updates).

Usage: `/update-doc`
