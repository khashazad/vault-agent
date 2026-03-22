# Taxonomy Page Refinements — Design Spec

## Goal

Three targeted fixes to the taxonomy page: full-height layout, right-click context menu for curation, and image attachment filtering from link targets.

## Changes

### 1. Full-height layout (frontend only)

**Problem:** The main list card is constrained by a `max-h-[480px]` scroll container and sits in a 2/3 + 1/3 grid with a stats/actions sidebar. Doesn't fill the viewport.

**Solution:**
- Outer wrapper: `flex flex-col flex-1 min-h-0` (matches LibraryPage pattern)
- Remove the right sidebar (stats panel + curation actions card) — curation moves to context menu, stats can be a compact inline bar above the list
- List card takes full width, uses `flex-1 overflow-y-auto` to fill remaining height
- Remove `max-h-[480px]` cap
- Keep: header row (title + refresh button), tab bar, search input on tags tab

**Stats display:** Move the 4 stat values (total notes, unique tags, folders, link targets) into a compact horizontal bar between the tab bar and the list content. Small inline badges, not large stat cards.

**Files:** `ui/src/pages/TaxonomyPage.tsx`

### 2. Right-click context menu (frontend only)

**Problem:** Curation actions (rename, merge, delete) are buttons in a sidebar panel. User must type the target name manually.

**Solution:**
- Right-click on any tag/folder/link row opens a context menu at cursor position
- Menu items depend on entity type:
  - **Tags:** Rename Tag, Merge Tags, Delete Tag
  - **Folders:** Rename Folder
  - **Links:** Rename Link, Merge Links
- Clicking a menu item opens the existing curation modal with `target` pre-filled from the clicked item
- Context menu dismissed on: outside click, Escape key, scroll, menu item click
- Prevent browser default context menu on these rows via `onContextMenu`

**Implementation:** A `ContextMenu` component (inline in TaxonomyPage, not a separate file — it's small) positioned absolutely at `{x, y}` from the mouse event. State: `contextMenu: { x: number, y: number, target: string, type: "tag" | "folder" | "link" } | null`.

**Files:** `ui/src/pages/TaxonomyPage.tsx`

### 3. Filter image attachments from link targets (backend)

**Problem:** `extract_wikilinks()` captures all `[[...]]` patterns including image embeds like `![[photo.png]]`. These show up as link targets in the taxonomy.

**Solution:** In `build_vault_taxonomy()`, filter the `link_counter` before building the response. Exclude entries where the title ends with any common image/attachment extension.

```python
IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".ico",
})

# In build_vault_taxonomy(), before building links list:
links = [
    LinkTargetInfo(title=t, count=c)
    for t, c in sorted(link_counter.items(), key=lambda x: -x[1])
    if not any(t.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
]
```

**Why filter here, not in `extract_wikilinks()`:** Other callers of `extract_wikilinks()` (like `build_vault_map()`) may want all links including embeds. The taxonomy builder is the right place to decide what's relevant for taxonomy display.

**Files:** `src/vault/taxonomy.py`, `tests/unit/test_taxonomy.py`

## Testing

- **Backend:** Add test for image filtering in `TestBuildVaultTaxonomy` — add a note with `![[photo.png]]` embed to `tmp_vault`, verify it's excluded from `link_targets`
- **Frontend:** Update `TaxonomyPage.test.tsx` — adjust selectors for new layout (no sidebar, stats bar), add test for context menu appearance on right-click
- **Existing tests:** May need selector adjustments if DOM structure changes significantly

## Out of scope

- No changes to curation backend logic
- No changes to API response shape
- No changes to other pages
