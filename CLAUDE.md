# CLAUDE.md — Vault Agent

## Project Overview

A **FastAPI backend server** running on Python that takes web/PDF highlights and intelligently integrates them into an Obsidian vault using Claude as the AI reasoning layer. Highlights are submitted via HTTP API, processed by a Claude agent with vault-aware tools, and written to the filesystem as Obsidian-compatible markdown.

## Architecture

```
HTTP Request (highlight payload)
  → FastAPI server

  Preview (POST /highlights/preview or /highlights/preview-batch):
    → Agent runs in dry-run mode (virtual filesystem)
    → Claude calls search_vault, reads notes, reports routing decision
    → Tool calls intercepted: diffs computed against originals
    → Proposed changes collected into a Changeset (persisted in SQLite)
    → Response: full Changeset with diffs and routing info

  Regenerate (POST /changesets/{id}/regenerate):
    → Client provides feedback on a pending changeset
    → Agent re-runs with original highlights + feedback
    → New changeset created, linked to parent via parent_changeset_id

  Apply (POST /changesets/{id}/apply):
    → Client approves/rejects individual changes
    → Approved changes written to vault filesystem
```

### Key Modules

- **`src/server.py`** — FastAPI entry point. Route definitions, middleware, request validation.
- **`src/models.py`** — Pydantic models (`HighlightInput`, `VaultNote`, `VaultMap`, etc.).
- **`src/config.py`** — Loads env vars, validates VAULT_PATH and API key.
- **`src/vault/reader.py`** — Scans the Obsidian vault filesystem. Parses frontmatter, extracts wikilinks, builds the vault map string for the LLM context.
- **`src/vault/writer.py`** — Filesystem write operations: create note, append to note. All operations are additive-only (no destructive edits).
- **`src/agent/agent.py`** — The core agent loop. Sends messages to Claude with tools, executes tool calls, loops until completion.
- **`src/agent/tools.py`** — Tool definitions and handlers for `search_vault`, `report_routing_decision`, `read_note`, `create_note`, `update_note`.
- **`src/agent/prompts.py`** — System prompt templates. The vault map gets interpolated into the system prompt at runtime.
- **`src/store.py`** — SQLite-backed persistent `ChangesetStore` using WAL journal mode. Stores changesets in `.changesets.db`.
- **`src/agent/changeset.py`** — `apply_changeset(vault_path, changeset, approved_ids?)`. Iterates approved `ProposedChange` objects and dispatches to `create_note` / `update_note`.
- **`src/agent/diff.py`** — `generate_diff(path, original, proposed)`. Wraps `difflib.unified_diff` to produce unified diffs for display in the UI.
- **`src/rag/chunker.py`** — Heading-based markdown chunker. Splits notes into chunks by heading boundaries.
- **`src/rag/embedder.py`** — Voyage AI wrapper for embedding texts and queries.
- **`src/rag/store.py`** — LanceDB wrapper for vector storage and search.
- **`src/rag/indexer.py`** — Orchestrator: scans vault → chunks notes → embeds changed chunks → upserts into LanceDB.
- **`src/rag/search.py`** — Hybrid search: combines vector similarity + full-text search with RRF (Reciprocal Rank Fusion) reranking. Falls back to vector-only if hybrid fails.
- **`src/vault/__init__.py`** — Path validation utility (`validate_path`) preventing traversal outside vault root.

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **LLM**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) via `anthropic` Python SDK (direct SDK, no framework)
- **Markdown parsing**: `python-frontmatter` for frontmatter, regex for wikilink extraction
- **Embeddings**: Voyage AI (`voyage-3-lite`, 512 dimensions) for semantic search
- **Search**: Hybrid vector + full-text search with RRF reranking via LanceDB
- **Vector store**: LanceDB (local, file-based) for chunk storage, vector search, and FTS index
- **Changeset storage**: SQLite with WAL journal mode (`.changesets.db`)
- **Filesystem**: `pathlib.Path.rglob()` for vault traversal, `Path.read_text()` / `.write_text()` for I/O
- **UI**: React 19, TypeScript 5.6, Vite 6, Tailwind CSS 4

## Commands

```bash
uv sync                                            # Install dependencies
uv run python -m src.server                        # Start server with hot reload (port 3000)
uv run uvicorn src.server:app --reload --port 3000 # Alternative start command
cd ui && bun install                               # Install UI dependencies
cd ui && bun run dev                               # Start UI dev server (port 5173)
cd ui && bun run build                             # Build UI for production → ui/dist/
```

## UI

A React 19 + TypeScript single-page application built with Vite 6 and Tailwind CSS 4.

### Views
- **Preview** — Submit highlights, review proposed changes (diffs), approve/reject individual changes, regenerate with feedback
- **Search** — Semantic search across vault contents
- **History** — Browse past changesets and their statuses

### Features
- Obsidian-aware markdown rendering (wikilinks, embeds, tags, callouts)
- Structured diff viewer with line numbers and collapsible sections

### Development
- Dev server on port 5173 with proxy to backend at port 3000
- Production build served from `ui/dist/`

## API Endpoints

- `GET /health` — Health check, returns vault path and status
- `GET /vault/map` — Returns vault structure JSON (for debugging)
- `POST /vault/index` — Index vault into LanceDB for semantic search
- `GET /vault/search?q=...&n=10` — Semantic search across vault contents
- `POST /highlights/preview` — Process a highlight through the agent in dry-run mode; returns Changeset
- `POST /highlights/preview-batch` — Process multiple highlights (max 50) in a single request; returns Changeset
- `GET /changesets` — List all changesets
- `GET /changesets/{id}` — Get full changeset with all ProposedChange details
- `PATCH /changesets/{id}/changes/{change_id}` — Set individual change status to `"approved"` | `"rejected"`
- `POST /changesets/{id}/apply` — Apply approved changes to disk; optional body: `{ change_ids: [...] }`
- `POST /changesets/{id}/reject` — Reject entire changeset and all its changes
- `POST /changesets/{id}/regenerate` — Re-run agent with original highlights + feedback; creates new linked changeset

### Changeset lifecycle

- Changesets are persisted in SQLite; no automatic expiry
- Changeset status: `pending` → `applied` | `rejected` | `partially_applied`
- Individual change status: `pending` → `approved` | `rejected` | `applied`
- Regeneration creates a new changeset linked via `parent_changeset_id`

### Highlight payload format

```json
{
  "text": "The highlighted text",
  "source": "URL or document title",
  "annotation": "Optional user note"
}
```

## Environment Setup

Required in `.env` (loaded via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
VAULT_PATH=/absolute/path/to/obsidian/vault
PORT=3000
VOYAGE_API_KEY=pa-...          # Required — powers semantic search
LANCEDB_PATH=.lancedb          # Optional — default ".lancedb"
CHANGESET_DB_PATH=.changesets.db  # Optional — default ".changesets.db"
```

`VAULT_PATH` must point to the root of the Obsidian vault (the directory containing `.obsidian/`).
`VOYAGE_API_KEY` is required. The agent uses semantic search (Voyage AI + LanceDB) to discover relevant notes.

## Key Design Decisions

### Hybrid search with Voyage AI + LanceDB
A compact vault summary (folder structure and top tags) is passed in the Claude context window. Hybrid search powers note discovery: notes are chunked by heading, embedded via Voyage AI (`voyage-3-lite`), and stored in LanceDB with a full-text search index. The agent uses `search_vault` which combines vector similarity and FTS results via RRF (Reciprocal Rank Fusion) reranking. Falls back to vector-only search if hybrid fails. Indexing is incremental (only re-embeds changed chunks).

### Additive-only writes
Two write operations: create note and append section. No modifications to existing prose, no deletions, no moves, no renames. Worst case is an unwanted new note or a bad append, both trivially reverted with `git checkout`.

### Direct Anthropic SDK
The agent loop is ~50 lines. No LangChain/LlamaIndex — a framework adds complexity without value for this use case.

### Changeset approval workflow
Highlights are previewed before being written. `POST /highlights/preview` runs the agent in dry-run mode using a virtual filesystem: tool calls are intercepted, diffs computed against originals, and a `Changeset` persisted to SQLite without touching the vault. The agent pre-fetches notes found via `search_vault` into the virtual filesystem before running. The client approves or rejects individual changes, then calls `POST /changesets/{id}/apply` to write only approved changes. Changesets can be regenerated with feedback via `POST /changesets/{id}/regenerate`. Git remains useful for reviewing what landed, but the primary safety mechanism is the approval gate.

### Routing decisions
The agent must call `report_routing_decision` exactly once before making any `create_note` or `update_note` calls. This declares the intended placement (update existing vs. create new), target path, reasoning, and confidence score. Routing decisions are stored on the changeset and displayed in the UI for review.

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

## Agent Tool Definitions

### `read_note`
- **Input**: `{ path: string }` — relative path from vault root
- **Output**: Full file content including frontmatter
- **Error**: `"Note not found: {path}"` if missing

### `create_note`
- **Input**: `{ path: string, content: string }`
- **Output**: Confirmation with created path
- **Constraint**: Must not overwrite existing files

### `update_note`
- **Input**: `{ path: string, operation: "append_section", heading?, content? }`
- **Operations**:
  - `append_section`: Appends content under a heading (or at end of file if heading omitted/not found)
- **Constraint**: Append-only, never removes content

### `search_vault`
- **Input**: `{ query: string, n?: number }`
- **Output**: Ranked list of note sections with path, heading, content snippet, and similarity score
- **Usage**: Agent calls this first to find semantically relevant notes before reading/creating

### `report_routing_decision`
- **Input**: `{ action: "update" | "create", target_path?: string, reasoning: string, confidence: number }`
- **Output**: Confirmation that routing decision was recorded
- **Constraint**: Must be called exactly once before any `create_note` or `update_note` calls

## File Structure

```
vault-agent/
├── CLAUDE.md
├── .env                   # gitignored
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── src/
│   ├── server.py
│   ├── models.py
│   ├── config.py
│   ├── store.py               # SQLite changeset store
│   ├── vault/
│   │   ├── __init__.py        # validate_path()
│   │   ├── reader.py
│   │   └── writer.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── tools.py
│   │   ├── prompts.py
│   │   ├── changeset.py       # Applies approved changes to vault
│   │   └── diff.py            # Unified diff generation
│   └── rag/
│       ├── __init__.py
│       ├── chunker.py
│       ├── embedder.py
│       ├── store.py
│       ├── indexer.py
│       └── search.py
├── ui/
│   └── src/
│       ├── main.tsx           # Entry point
│       ├── App.tsx            # Root component, routing
│       ├── types.ts           # TypeScript type definitions
│       ├── styles.css
│       ├── utils.ts
│       ├── api/               # API client
│       ├── components/        # React components
│       ├── hooks/             # Custom React hooks
│       └── utils/             # Utility modules
├── .github/
│   └── workflows/
│       ├── claude.yml
│       └── claude-code-review.yml
├── test-highlights/
│   └── highlights.json
└── .claude/
    └── plans/                 # Saved implementation plans
```
