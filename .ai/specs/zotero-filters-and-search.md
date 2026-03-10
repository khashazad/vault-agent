# Zotero Papers Filters & Search

## Why

Users browsing their Zotero library can't narrow results — they must scroll through all papers to find the subset they are looking for. Search exists but the UI doesn't make filter state obvious. Adding filters and improving search discoverability lets users quickly find what needs processing.

## What

- Sync status filter (All / Synced / Not Synced) on the papers step
- "Not Synced" is the default filter, and additionally filters to only papers with annotations (actionable papers)
- Search bar already works (title + author) — ensure it's prominent and clear
- No counts on filter buttons
- Filters reset pagination and compose with collection selection

Done when: user lands on Zotero page and sees only unsynced papers with annotations by default; can toggle between filter states; can combine with search + collection selection.

## Context

**Relevant files:**
- `ui/src/components/ZoteroSync.tsx` — main component, owns papers state, search, pagination (738 lines)
- `ui/src/api/client.ts` — `fetchZoteroPapers(opts)` — currently accepts `search`, `collectionKey`, `offset`, `limit`
- `ui/src/types.ts` — `ZoteroPaperSummary`, `ZoteroPapersResponse`
- `src/server.py` — `GET /zotero/papers` route handler (lines 379-421)
- `src/zotero/sync.py` — `get_cached_papers_paginated()` — SQLite query with LIKE search (lines 196-220), `zotero_paper_sync` table has `last_synced` column; `zotero_papers` table has `annotation_count` column

**Patterns to follow:**
- Debounced search already in ZoteroSync.tsx (300ms) — reuse same pattern for filter state
- Collection filter resets page to 0 on change — sync filter should do the same
- Tailwind classes: `bg-surface border border-border rounded px-3 py-2 text-sm text-foreground`
- Status badges: `bg-green-bg text-green` (synced), `bg-surface text-muted border border-border` (never synced)

**Key decisions:**
- Sync status filter is server-side (SQL JOIN with `zotero_paper_sync` table + `annotation_count` filter), not client-side
- Default filter: "Not Synced" with `annotation_count > 0` — shows only actionable papers
- Search already covers title + authors via `LIKE` — no backend search changes needed
- Filter UI goes in the papers step, between the search bar and the paper list
- No counts on filter buttons

## Constraints

**Must:**
- Reset pagination to page 0 when any filter changes
- Compose with existing collection selection and search
- Work for both cached papers (no collection) and collection-filtered papers (live fetch)
- Follow existing Tailwind theme tokens (`bg-surface`, `text-muted`, `border-border`, etc.)

**Must not:**
- Add new dependencies
- Refactor existing search or pagination logic
- Change the annotations or processing steps

**Out of scope:**
- Year range filter, item type filter, sorting options (future work)
- Advanced search syntax (AND/OR operators)
- Counts on filter buttons

## Tasks

### T1: Backend — add sync_status filter param to GET /zotero/papers

**Do:**
1. In `src/zotero/sync.py` → `get_cached_papers_paginated()`: accept optional `sync_status` param (`"all"` | `"synced"` | `"unsynced"`)
   - `"synced"`: LEFT JOIN `zotero_paper_sync` WHERE `last_synced IS NOT NULL`
   - `"unsynced"`: LEFT JOIN `zotero_paper_sync` WHERE (`last_synced IS NULL` or no row) AND `annotation_count > 0`
   - `"all"` / None: current behavior (no filter)
   - Apply same filter to the COUNT query for correct totals
2. In `src/server.py` → `GET /zotero/papers`: accept `sync_status` query param, pass to `get_cached_papers_paginated()`
3. For live collection fetch path: apply same in-memory sync_status filter using `paper.last_synced` and `paper.annotation_count`

**Files:** `src/zotero/sync.py`, `src/server.py`

**Verify:** `curl "localhost:3000/zotero/papers?sync_status=unsynced"` returns only papers with `last_synced: null` AND `annotation_count > 0`; `?sync_status=synced` returns only papers with non-null `last_synced`; omitting param or `?sync_status=all` returns all.

### T2: Frontend — add sync status filter + refine search UI

**Do:**
1. In `ui/src/api/client.ts`: add `syncStatus` to `fetchZoteroPapers` options, pass as `sync_status` query param
2. In `ui/src/components/ZoteroSync.tsx`:
   - Add `syncStatus` state: `"all" | "synced" | "unsynced"` (default `"unsynced"`)
   - Render filter bar between search input and paper list: three toggle buttons (All / Synced / Not Synced)
   - Style active button with `bg-accent/15 text-accent` (matches collection tree active style)
   - Inactive buttons: `bg-surface text-muted border border-border`
   - On filter change: set syncStatus, reset page to 0
   - Pass `syncStatus` to `loadPapers()` → `fetchZoteroPapers()`
   - Do NOT reset syncStatus when collection changes (user likely wants to keep filtering unsynced across collections)
3. Add placeholder text to search input: "Search by title or author..."

**Files:** `ui/src/api/client.ts`, `ui/src/components/ZoteroSync.tsx`

**Verify:** Manual: page loads with "Not Synced" active → only unsynced papers with annotations shown; toggle to "All" → all papers shown; combine with search → both filters apply; switch collection → sync filter persists; pagination updates correctly.

## Done

- [ ] `curl "localhost:3000/zotero/papers?sync_status=unsynced&search=foo"` returns correct filtered + searched results with accurate total count
- [ ] Manual: page defaults to "Not Synced" filter showing only actionable papers
- [ ] Manual: toggle each sync status filter, verify paper list updates
- [ ] Manual: combine sync filter + search + collection selection — all three compose correctly
- [ ] Manual: pagination shows correct page count after filtering
- [ ] No regressions in annotations step or processing step
