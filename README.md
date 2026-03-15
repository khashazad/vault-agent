# Vault Agent

An AI-powered bridge between your Zotero annotations and your Obsidian vault.

## The Problem

When you annotate papers in Zotero or highlight passages while reading, those annotations sit trapped. They never make it into your knowledge base in a meaningful, connected way. You end up with a pile of disconnected snippets instead of an integrated second brain.

## What Vault Agent Does

Connect your Zotero library and Vault Agent's AI figures out where each annotation belongs in your existing Obsidian vault. It proposes changes — new notes or appends to existing ones — with proper wikilinks, tags, and frontmatter. You review diffs and approve or reject each change before anything touches your files.

## How It Works

1. **Browse** — Browse your Zotero papers by collection, search, or sync status in the web UI.
2. **Select** — Pick a paper and review its annotations. Toggle individual annotations on/off.
3. **Search & Reason** — The AI agent reviews your vault structure, reads relevant notes, and decides the best placement: update an existing note, create a new one, or skip. It declares a routing decision explaining its reasoning.
4. **Preview** — Proposed changes are computed against your current files and presented as diffs. Nothing is written to disk yet.
5. **Approve & Apply** — Review each proposed change individually. Approve what looks good, reject what doesn't. Only approved changes are written to your vault.

The safety model is deliberate: all writes are **additive-only** (appends and new files — no deletions, no modifications to existing prose), and every change goes through an **approval gate** before touching disk.

## Technology Overview

**Claude (Haiku 4.5)** — The AI reasoning layer that reads your vault, decides where annotations belong, and generates Obsidian-compatible markdown. The agent loop uses the Anthropic SDK directly — no framework — keeping the core logic minimal and transparent.

**pyzotero** — Connects to your Zotero library to fetch papers, annotations, and collections. Background sync keeps a local cache up to date.

**FastAPI** — Async Python API server. Serves the REST API and the production UI build.

**SQLite (WAL mode)** — Persists changesets across server restarts. Lightweight, zero-config, no external database needed.

**React + Vite + Tailwind** — The review UI. Features Obsidian-aware markdown rendering (wikilinks, callouts, embeds), a structured diff viewer, and a Zotero paper/annotation browser.

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Bun](https://bun.sh/) (for the UI)
- An Obsidian vault on your local filesystem
- An [Anthropic](https://console.anthropic.com/) API key
- Optional: [Zotero](https://www.zotero.org/) API key and library ID for Zotero integration

### Setup

```bash
# Clone and install
git clone https://github.com/khashazad/vault-agent.git
cd vault-agent
uv sync
cd ui && bun install && cd ..

# Configure environment
cp .env.example .env
# Edit .env with your API keys and vault path:
#   ANTHROPIC_API_KEY=sk-ant-...
#   VAULT_PATH=/absolute/path/to/your/obsidian/vault
#   ZOTERO_API_KEY=...          (optional)
#   ZOTERO_LIBRARY_ID=...       (optional)

# Start the backend
uv run python -m src.server

# Start the UI (in another terminal)
cd ui && bun run dev
```

The backend runs on port 3456 and the UI dev server on port 5173.

### Running Tests

```bash
# Backend (pytest — 138 tests)
uv sync --dev
uv run pytest tests/ -v

# Frontend (vitest — 46 tests)
cd ui && bun run test

# E2E (Playwright — 19 tests, requires built UI)
cd ui && bun run build
cd ../tests/e2e && bun install && bunx playwright install chromium
bunx playwright test
```

CI runs all three suites on push/PR to `main` via GitHub Actions.

### Detailed Reference

See [CLAUDE.md](./CLAUDE.md) for full API documentation, agent tool definitions, testing architecture, file structure, and internal architecture details.

## Local Only

Vault Agent has no authentication and is designed for **local use only** — it runs on your machine against your local vault. Do not expose it to the public internet.
