# Zotero-Only Cleanup

## Why

The app currently supports multiple content sources (web highlights, book highlights, Zotero annotations) but only Zotero is actively used. The generic highlight pipeline adds dead code, confusing UI tabs, and maintenance burden. Stripping it focuses the codebase on what matters.

## What

Remove all non-Zotero entry points, UI views, and source type variants. The shared infrastructure (agent, changesets, RAG, vault I/O) stays — Zotero depends on it.

## Context

**Relevant files:**

Backend (modify):
- `src/server.py` — has 4 dead endpoints (content/preview, preview-batch, changesets list, regenerate)
- `src/models/content.py` — SourceType includes "web"/"book", SourceMetadata has web/book fields, BatchContentInput unused
- `src/models/changesets.py` — RegenerateRequest unused, Changeset has migration validator for old "highlights" key
- `src/models/__init__.py` — re-exports dead models
- `src/agent/prompts.py` — SOURCE_CONFIGS has "web"/"book" entries

Frontend (delete):
- `ui/src/components/ContentPreview.tsx` — generic highlight submission + changeset list
- `ui/src/components/ContentForm.tsx` — highlight input form
- `ui/src/components/ChangesetHistory.tsx` — standalone changeset history view
- `ui/src/components/StatusBadge.tsx` — only used by ContentPreview + ChangesetHistory
- `ui/src/hooks/useChangesets.ts` — changeset state management for generic flow

Frontend (modify):
- `ui/src/App.tsx` — remove preview/history views, useChangesets hook
- `ui/src/components/Layout.tsx` — remove "Review"/"History" nav tabs
- `ui/src/api/client.ts` — remove dead API functions
- `ui/src/types.ts` — remove dead types, simplify SourceMetadata
- `ui/src/utils.ts` — remove `confidenceClass`, `routingActionClass`
- `ui/src/components/ZoteroSync.tsx` — remove "Open in Review tab" button + `onViewChange` prop

Frontend (delete, additional):
- `ui/src/components/VaultSearch.tsx` — Search tab removed per user request

Frontend (keep unchanged):
- `ChangesetReview.tsx`, `DiffViewer.tsx` — used by ZoteroSync for changeset approval
- `MarkdownPreview.tsx`, `ErrorAlert.tsx`, `CollectionTree.tsx`

Backend (keep unchanged):
- `src/agent/agent.py`, `tools.py` — generate_changeset() called by Zotero orchestrator
- `src/agent/changeset.py`, `diff.py` — apply approved changes
- `src/store.py` — changeset persistence
- `src/zotero/*` — all Zotero modules
- `src/rag/*`, `src/vault/*` — shared infrastructure

**Dependency chain (why changeset infra stays):**
```
ZoteroSync.tsx → ChangesetReview.tsx → { fetchChangeset, updateChangeStatus, applyChangeset, rejectChangeset }
                                        → DiffViewer.tsx
ZoteroOrchestrator → generate_changeset() → agent.py → tools.py, prompts.py
                                           → changeset_store (persistence)
```

**Changeset endpoints still needed by Zotero UI:**
- `GET /changesets/{id}` — fetch changeset for review
- `PATCH /changesets/{id}/changes/{change_id}` — approve/reject individual changes
- `POST /changesets/{id}/apply` — write approved changes to vault
- `POST /changesets/{id}/reject` — reject changeset

## Constraints

**Must:**
- Keep all changeset CRUD endpoints (GET/PATCH/POST) used by ChangesetReview
- Keep agent system, changeset store, RAG, vault modules untouched
- Keep `url` field on SourceMetadata (Zotero uses it)

**Must not:**
- Break the Zotero sync → changeset review → apply flow
- Remove ChangesetReview or DiffViewer (ZoteroSync imports them)
- Touch any file in `src/zotero/`, `src/rag/`, `src/vault/`, or `src/agent/agent.py`

**Out of scope:**
- Updating CLAUDE.md project docs (separate task)
- Renaming ContentItem/SourceMetadata to Zotero-specific names (unnecessary churn)
- Removing backend `/vault/search` or `/vault/index` endpoints (still useful via API/curl; only the UI tab goes)

## Tasks

### T1: Backend — remove dead endpoints and models

**Do:**
1. `src/server.py` — delete endpoints: `POST /content/preview`, `POST /content/preview-batch`, `GET /changesets`, `POST /changesets/{id}/regenerate`. Remove imports: `BatchContentInput`, `RegenerateRequest`, `ContentItem`. Remove comment `# --- Content preview ---`.
2. `src/models/content.py` — change `SourceType` to `Literal["zotero"]`. Remove `BatchContentInput`. Remove fields from SourceMetadata: `site_name`, `isbn`, `chapter`, `page_range`. Change ContentItem.source_type default to `"zotero"`.
3. `src/models/changesets.py` — delete `RegenerateRequest`. Change Changeset.source_type default to `"zotero"`. Remove `_migrate_highlights` validator.
4. `src/models/__init__.py` — remove `BatchContentInput`, `RegenerateRequest` from imports and `__all__`.
5. `src/agent/prompts.py` — remove "web" and "book" from `SOURCE_CONFIGS`. Keep only "zotero".

**Files:** `src/server.py`, `src/models/content.py`, `src/models/changesets.py`, `src/models/__init__.py`, `src/agent/prompts.py`

**Verify:** `uv run python -c "from src.server import app; print('OK')"` — server imports clean. `uv run python -c "from src.models import Changeset, ContentItem; print(ContentItem(text='t', source='s').source_type)"` — prints "zotero".

### T2: Frontend — remove dead components and views

**Do:**
1. Delete files: `ContentPreview.tsx`, `ContentForm.tsx`, `ChangesetHistory.tsx`, `StatusBadge.tsx`, `VaultSearch.tsx`, `useChangesets.ts`
2. `App.tsx` — remove all view switching (state, useChangesets, handleDone). Render `<ZoteroSync />` directly. Remove `onViewChange` prop.
3. `Layout.tsx` — keep only `{ label: "Zotero", view: "zotero" }` in NAV_ITEMS.
4. `api/client.ts` — remove `previewContent`, `previewContentBatch`, `fetchChangesets`, `regenerateChangeset`, `searchVault`. Remove type imports: `ContentItem`, `ChangesetSummary`, `SearchResponse`.
5. `types.ts` — remove `SourceType`, `SourceMetadata`, `ContentItem`, `ChangesetSummary`, `ChunkInfo`, `SearchResponse`. Keep `Changeset`, `ProposedChange`, `RoutingInfo` (used by ChangesetReview).
6. `utils.ts` — remove `confidenceClass`, `routingActionClass`. Keep `formatError`.
7. `ZoteroSync.tsx` — remove `onViewChange` prop and "Open in Review tab" button (lines 752-757).

**Files:** 6 deletions + `App.tsx`, `Layout.tsx`, `client.ts`, `types.ts`, `utils.ts`, `ZoteroSync.tsx`

**Verify:** `cd ui && bun run build` — clean build. Manual: UI shows only Zotero, sync flow works end-to-end.

## Done

- [ ] `uv run python -c "from src.server import app"` — no import errors
- [ ] `cd ui && bun run build` — clean build
- [ ] Manual: UI shows only Zotero tab
- [ ] Manual: Zotero paper sync → changeset review → approve → apply still works
- [ ] No references to "web", "book", "preview", "history", "search" in active UI code
