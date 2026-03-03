# CLAUDE.md — Vault Agent

## Project Overview

A **FastAPI backend server** running on Python that takes web/PDF highlights and intelligently integrates them into an Obsidian vault using Claude as the AI reasoning layer. Highlights are submitted via HTTP API, processed by a Claude agent with vault-aware tools, and written to the filesystem as Obsidian-compatible markdown.

## Architecture

```
HTTP Request (highlight payload)
  → FastAPI server

  PATH A — Direct write (POST /highlights/process):
    → Agent sends highlight + vault context to Claude
    → Claude uses tools to read/create/update notes
    → Changes written to vault filesystem immediately
    → Response returned with affected notes + reasoning

  PATH B — Preview + approval (POST /highlights/preview):
    → Agent runs in dry-run mode, streams events via SSE
    → Proposed changes (diffs) collected into a Changeset
    → Client approves/rejects individual changes
    → POST /changesets/{id}/apply writes approved changes to disk
```

### Key Modules

- **`src/server.py`** — FastAPI entry point. Route definitions, middleware, request validation.
- **`src/models.py`** — Pydantic models (`HighlightInput`, `VaultNote`, `VaultMap`, etc.).
- **`src/config.py`** — Loads env vars, validates VAULT_PATH and API key.
- **`src/vault/reader.py`** — Scans the Obsidian vault filesystem. Parses frontmatter, extracts wikilinks, builds the vault map string for the LLM context.
- **`src/vault/writer.py`** — Filesystem write operations: create note, append to note, update frontmatter. All operations are additive-only (no destructive edits).
- **`src/agent/agent.py`** — The core agent loop. Sends messages to Claude with tools, executes tool calls, loops until completion.
- **`src/agent/tools.py`** — Tool definitions and handlers for `read_note`, `create_note`, `update_note`, `search_vault`.
- **`src/agent/prompts.py`** — System prompt templates. The vault map gets interpolated into the system prompt at runtime.
- **`src/store.py`** — In-memory `ChangesetStore`. Holds pending changesets keyed by ID. Auto-expires entries older than 1 hour on `cleanup()`.
- **`src/agent/changeset.py`** — `apply_changeset(vault_path, changeset, approved_ids?)`. Iterates approved `ProposedChange` objects and dispatches to `create_note` / `update_note`.
- **`src/agent/diff.py`** — `generate_diff(path, original, proposed)`. Wraps `difflib.unified_diff` to produce unified diffs for display in the UI.
- **`src/rag/chunker.py`** — Heading-based markdown chunker. Splits notes into chunks by heading boundaries.
- **`src/rag/embedder.py`** — Voyage AI wrapper for embedding texts and queries.
- **`src/rag/store.py`** — LanceDB wrapper for vector storage and search.
- **`src/rag/indexer.py`** — Orchestrator: scans vault → chunks notes → embeds changed chunks → upserts into LanceDB.
- **`src/rag/search.py`** — Semantic search: embeds query → vector search → returns ranked results.

## Tech Stack

- **Runtime**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **LLM**: Claude Sonnet 4.5 via `anthropic` Python SDK (direct SDK, no framework)
- **Markdown parsing**: `python-frontmatter` for frontmatter, regex for wikilink extraction
- **Embeddings**: Voyage AI (`voyage-3-lite`, 512 dimensions) for semantic search
- **Vector store**: LanceDB (local, file-based) for chunk storage and vector search
- **Filesystem**: `pathlib.Path.rglob()` for vault traversal, `Path.read_text()` / `.write_text()` for I/O

## Commands

```bash
uv sync                                            # Install dependencies
uv run python -m src.server                        # Start server with hot reload (port 3000)
uv run uvicorn src.server:app --reload --port 3000 # Alternative start command
```

## API Endpoints

- `GET /health` — Health check, returns vault path and status
- `GET /vault/map` — Returns vault structure JSON (for debugging)
- `POST /vault/index` — Index vault into LanceDB for semantic search (requires VOYAGE_API_KEY)
- `GET /vault/search?q=...&n=10` — Semantic search across vault contents (requires VOYAGE_API_KEY)
- `POST /highlights/process` — Process a highlight through the agent (direct write)
- `POST /highlights/preview` — SSE stream of agent reasoning + proposed changes; returns Changeset (409 if preview in progress)
- `GET /changesets` — List all changesets (triggers cleanup of expired ones)
- `GET /changesets/{id}` — Get full changeset with all ProposedChange details
- `PATCH /changesets/{id}/changes/{change_id}` — Set individual change status to `"approved"` | `"rejected"`
- `POST /changesets/{id}/apply` — Apply approved changes to disk; optional body: `{ change_ids: [...] }`
- `POST /changesets/{id}/reject` — Reject entire changeset and all its changes

### Changeset lifecycle

- Changesets expire and are cleaned up after **1 hour**
- Changeset status: `pending` → `applied` | `rejected` | `partially_applied`
- Individual change status: `pending` → `approved` | `rejected` | `applied`

### Highlight payload format

```json
{
  "text": "The highlighted text",
  "source": "URL or document title",
  "annotation": "Optional user note",
  "tags": ["optional", "suggested", "tags"]
}
```

## Environment Setup

Required in `.env` (loaded via `python-dotenv`):

```
ANTHROPIC_API_KEY=sk-ant-...
VAULT_PATH=/absolute/path/to/obsidian/vault
PORT=3000
VOYAGE_API_KEY=pa-...          # Optional — enables RAG semantic search
LANCEDB_PATH=.lancedb          # Optional — default ".lancedb"
```

`VAULT_PATH` must point to the root of the Obsidian vault (the directory containing `.obsidian/`).
`VOYAGE_API_KEY` is optional. When not set, RAG is disabled and the agent uses only vault structure (titles/tags/links) for context.

## Key Design Decisions

### Optional RAG with Voyage AI + LanceDB
The full vault structure (titles, folders, tags, link graph) is always passed in the Claude context window. When `VOYAGE_API_KEY` is set, semantic search is also available: notes are chunked by heading, embedded via Voyage AI (`voyage-3-lite`), and stored in LanceDB. The agent uses `search_vault` to find relevant note sections by meaning before reading/creating. Indexing is incremental (only re-embeds changed chunks).

### Additive-only writes
Three write operations: create note, append section, add tags. No modifications to existing prose, no deletions, no moves, no renames. Worst case is an unwanted new note or a bad append, both trivially reverted with `git checkout`.

### Direct Anthropic SDK
The agent loop is ~50 lines. No LangChain/LlamaIndex — a framework adds complexity without value for this use case.

### Changeset approval workflow
Highlights are previewed before being written. `POST /highlights/preview` runs the agent in dry-run mode: tool calls are intercepted, diffs computed, and a `Changeset` returned without touching the filesystem. The client approves or rejects individual changes, then calls `POST /changesets/{id}/apply` to write only approved changes. Git remains useful for reviewing what landed, but the primary safety mechanism is the approval gate.

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
- **Input**: `{ path: string, operation: "append_section" | "add_tags", heading?, content?, tags? }`
- **Operations**:
  - `append_section`: Appends content under a heading (or at end of file)
  - `add_tags`: Merges tags into frontmatter array (no duplicates)
- **Constraint**: Append-only, never removes content

### `search_vault` (RAG only — available when VOYAGE_API_KEY is set)
- **Input**: `{ query: string, n?: number }`
- **Output**: Ranked list of note sections with path, heading, content snippet, and similarity score
- **Usage**: Agent calls this first to find semantically relevant notes before reading/creating

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
│   ├── store.py               # In-memory changeset store
│   ├── vault/
│   │   ├── __init__.py
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
├── test-highlights/
│   └── highlights.json
└── .claude/
    └── plans/                 # Saved implementation plans
```
