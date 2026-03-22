# Taxonomy Page Refinements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three issues: full-height layout, right-click context menu for curation, and image attachment filtering from link targets.

**Architecture:** Backend change is a filter in `build_vault_taxonomy()`. Frontend changes are a layout restructure of `TaxonomyPage.tsx` — remove right sidebar, add context menu, make list fill viewport height.

**Tech Stack:** Python/FastAPI (backend), React 19/TypeScript/Tailwind (frontend), pytest (backend tests), vitest+MSW (frontend tests)

**Worktree:** `.worktrees/taxonomy` on branch `feat/taxonomy-vault-parse`

---

## File Structure

### Modified files
- `src/vault/taxonomy.py` — add image extension filter to `build_vault_taxonomy()`
- `tests/unit/test_taxonomy.py` — add image filtering test
- `tests/conftest.py` — add image embed to test vault fixture
- `ui/src/pages/TaxonomyPage.tsx` — layout rewrite: full-height, context menu, remove sidebar
- `ui/src/__tests__/components/TaxonomyPage.test.tsx` — update tests for new layout + add context menu test

---

## Task 1: Backend — Filter Image Attachments from Link Targets

**Files:**
- Modify: `src/vault/taxonomy.py:99-137`
- Modify: `tests/unit/test_taxonomy.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add image embed to test vault fixture**

In `tests/conftest.py`, update the `"Topics/Machine Learning.md"` note content to include an image embed. Change:
```python
"## Related\n\n[[Projects/My Project]]\n"
```
To:
```python
"## Related\n\n[[Projects/My Project]]\n\n![[diagram.png]]\n"
```

- [ ] **Step 2: Write failing test for image filtering**

Append to `tests/unit/test_taxonomy.py`:

```python
    def test_image_embeds_excluded_from_link_targets(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        link_titles = {lt.title for lt in taxonomy.link_targets}
        assert "diagram.png" not in link_titles
        # Non-image links still present
        assert "Machine Learning" in link_titles
        assert "Projects/My Project" in link_titles
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy && uv run pytest tests/unit/test_taxonomy.py::TestBuildVaultTaxonomy::test_image_embeds_excluded_from_link_targets -v`
Expected: FAIL — `assert "diagram.png" not in link_titles` fails because images are not yet filtered.

- [ ] **Step 4: Implement image filtering**

In `src/vault/taxonomy.py`, add constant after `FENCED_CODE_RE` (line 18):

```python
IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".ico",
})
```

Then in `build_vault_taxonomy()`, change the links list comprehension (lines 126-129) from:
```python
    links = [
        LinkTargetInfo(title=t, count=c)
        for t, c in sorted(link_counter.items(), key=lambda x: -x[1])
    ]
```
To:
```python
    links = [
        LinkTargetInfo(title=t, count=c)
        for t, c in sorted(link_counter.items(), key=lambda x: -x[1])
        if not any(t.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
    ]
```

- [ ] **Step 5: Run all taxonomy tests**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy && uv run pytest tests/unit/test_taxonomy.py -v`
Expected: All PASS (24 tests)

- [ ] **Step 6: Run full backend suite**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy && uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy
git add src/vault/taxonomy.py tests/unit/test_taxonomy.py tests/conftest.py
git commit -m "fix(vault): filter image attachments from taxonomy link targets"
```

---

## Task 2: Frontend — Full-Height Layout + Context Menu + Remove Sidebar

**Files:**
- Modify: `ui/src/pages/TaxonomyPage.tsx` — full rewrite of layout

This task rewrites the TaxonomyPage layout with three changes:
1. Full-height layout matching LibraryPage pattern (`flex flex-col flex-1 min-h-0`)
2. Remove right sidebar (stats + curation actions). Move stats to compact inline bar.
3. Add right-click context menu on tag/folder/link rows.

- [ ] **Step 1: Rewrite `TaxonomyPage.tsx`**

Replace the entire file content. Key structural changes:

**Layout wrapper:** Change outer div from:
```tsx
<div className="flex flex-col gap-5 py-6 px-8">
```
To:
```tsx
<div className="flex flex-col flex-1 min-h-0">
  {/* Header bar — fixed */}
  <div className="px-6 py-4 flex items-center justify-between shrink-0">
```

**Stats bar:** Replace the right sidebar stats panel with a compact horizontal bar between tabs and content:
```tsx
{taxonomy && (
  <div className="flex items-center gap-6 px-6 py-2 text-[11px] text-muted shrink-0">
    <span><strong className="text-text">{taxonomy.total_notes}</strong> notes</span>
    <span><strong className="text-text">{taxonomy.tags.length}</strong> tags</span>
    <span><strong className="text-text">{taxonomy.folders.length}</strong> folders</span>
    <span><strong className="text-text">{taxonomy.link_targets.length}</strong> links</span>
  </div>
)}
```

**Main content:** Single full-width card filling remaining height:
```tsx
<div className="flex-1 overflow-y-auto px-6 pb-4 min-h-0">
  <div className="glass-card p-4 flex flex-col gap-3 min-h-full">
```
Remove `max-h-[480px]` from the inner scroll container. Remove the `grid grid-cols-1 md:grid-cols-3` grid entirely. Remove the right panel (stats + curation actions cards).

**Context menu state:** Add new state:
```tsx
const [contextMenu, setContextMenu] = useState<{
  x: number;
  y: number;
  target: string;
  type: "tag" | "folder" | "link";
} | null>(null);
```

**Context menu handler:** For each row (tag, folder, link), add `onContextMenu`:
```tsx
onContextMenu={(e) => {
  e.preventDefault();
  setContextMenu({ x: e.clientX, y: e.clientY, target: itemName, type: "tag" });
}}
```

Apply to:
- Folder rows: `type: "folder"`, `target: f` (folder path string)
- Tag tree nodes: `type: "tag"`, `target: node.name` — pass `onContextMenu` as prop to `TagTreeNode`
- Tag filtered list rows: `type: "tag"`, `target: t.name`
- Link target rows: `type: "link"`, `target: lt.title`

**Context menu component** (inline, rendered at bottom of component return):
```tsx
{contextMenu && (
  <div
    className="fixed inset-0 z-40"
    onClick={() => setContextMenu(null)}
    onContextMenu={(e) => { e.preventDefault(); setContextMenu(null); }}
  >
    <div
      className="fixed z-50 bg-surface border border-white/10 rounded-lg shadow-xl py-1 min-w-[160px]"
      style={{ left: contextMenu.x, top: contextMenu.y }}
      onClick={(e) => e.stopPropagation()}
    >
      {contextMenu.type === "tag" && (
        <>
          <button
            className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
            onClick={() => { openModal("rename_tag", contextMenu.target); setContextMenu(null); }}
          >
            Rename Tag
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
            onClick={() => { openModal("merge_tags", contextMenu.target); setContextMenu(null); }}
          >
            Merge Tags
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-xs text-red hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
            onClick={() => { openModal("delete_tag", contextMenu.target); setContextMenu(null); }}
          >
            Delete Tag
          </button>
        </>
      )}
      {contextMenu.type === "folder" && (
        <button
          className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
          onClick={() => { openModal("rename_folder", contextMenu.target); setContextMenu(null); }}
        >
          Rename Folder
        </button>
      )}
      {contextMenu.type === "link" && (
        <>
          <button
            className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
            onClick={() => { openModal("rename_link", contextMenu.target); setContextMenu(null); }}
          >
            Rename Link
          </button>
          <button
            className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
            onClick={() => { openModal("merge_links", contextMenu.target); setContextMenu(null); }}
          >
            Merge Links
          </button>
        </>
      )}
    </div>
  </div>
)}
```

**Dismiss on Escape:** Add `useEffect` for keydown:
```tsx
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Escape") setContextMenu(null);
  };
  document.addEventListener("keydown", handleKeyDown);
  return () => document.removeEventListener("keydown", handleKeyDown);
}, []);
```

**TagTreeNode changes:** Add `onContextMenu` prop:
```tsx
function TagTreeNode({
  node, depth, expanded, onToggle, filter, onContextMenu,
}: {
  // ... existing props ...
  onContextMenu: (e: React.MouseEvent, name: string) => void;
}) {
```
On the row div, add: `onContextMenu={(e) => onContextMenu(e, node.name)}`
Pass it down recursively to children.

**Keep:** The curation modal (lines 480-553) stays unchanged. The modal is still opened by `openModal()` — now triggered from context menu instead of sidebar buttons.

**Remove entirely:**
- Right panel div (lines 384-477) — stats cards + curation action buttons
- The `grid grid-cols-1 md:grid-cols-3` wrapper

- [ ] **Step 2: Verify build succeeds**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy/ui && bun run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy
git add ui/src/pages/TaxonomyPage.tsx
git commit -m "feat(ui): full-height layout, context menu curation, remove sidebar"
```

---

## Task 3: Update Frontend Tests

**Files:**
- Modify: `ui/src/__tests__/components/TaxonomyPage.test.tsx`

Tests need updating because:
- Stats are now inline text (e.g., "142 notes") instead of standalone stat-value spans
- Context menu replaces sidebar curation buttons
- Layout is different (no grid)

- [ ] **Step 1: Rewrite `TaxonomyPage.test.tsx`**

```tsx
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, it, expect } from "vitest";
import { TaxonomyPage } from "../../pages/TaxonomyPage";
import { server } from "../handlers";
import { http, HttpResponse } from "msw";

function renderPage() {
  return render(
    <MemoryRouter>
      <TaxonomyPage />
    </MemoryRouter>,
  );
}

describe("TaxonomyPage", () => {
  it("shows loading then renders taxonomy data", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/142/)).toBeInTheDocument();
    });
  });

  it("renders tag hierarchy on default tab", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
      expect(screen.getByText("daily")).toBeInTheDocument();
      expect(screen.getByText("paper")).toBeInTheDocument();
    });
  });

  it("switches to folders tab", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /folders/i }));
    await waitFor(() => {
      expect(screen.getByText("Papers")).toBeInTheDocument();
      expect(screen.getByText("Topics")).toBeInTheDocument();
    });
  });

  it("switches to link targets tab", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /link targets/i }));
    await waitFor(() => {
      expect(screen.getByText("Machine Learning")).toBeInTheDocument();
    });
  });

  it("shows error on API failure", async () => {
    server.use(
      http.get("/vault/taxonomy", () =>
        HttpResponse.json({ detail: "No vault configured" }, { status: 400 }),
      ),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("filters tags by search", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    const search = screen.getByPlaceholderText(/filter/i);
    await user.type(search, "daily");
    expect(screen.getByText("daily")).toBeInTheDocument();
    expect(screen.queryByText("research")).not.toBeInTheDocument();
  });

  it("shows inline vault stats", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/142/)).toBeInTheDocument();
      expect(screen.getByText(/5/)).toBeInTheDocument();
    });
  });

  it("shows context menu on right-click of tag", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("research")).toBeInTheDocument();
    });

    const tagEl = screen.getByText("research");
    fireEvent.contextMenu(tagEl);
    await waitFor(() => {
      expect(screen.getByText("Rename Tag")).toBeInTheDocument();
      expect(screen.getByText("Merge Tags")).toBeInTheDocument();
      expect(screen.getByText("Delete Tag")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run frontend tests**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy/ui && bun run test`
Expected: All PASS

If tests fail due to DOM structure changes, adjust selectors. The key patterns:
- Stats: look for text content like `/142/` (partial match) instead of exact `"142"` in a standalone element
- Context menu: `fireEvent.contextMenu(element)` triggers `onContextMenu`
- Tab buttons: still `<button>` elements with text "Folders", "Tags", "Link Targets"

- [ ] **Step 3: Commit**

```bash
cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy
git add ui/src/__tests__/components/TaxonomyPage.test.tsx
git commit -m "test(ui): update TaxonomyPage tests for new layout + context menu"
```

---

## Task 4: Final Verification

- [ ] **Step 1: Run full backend tests**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy && uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run full frontend tests**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy/ui && bun run test`
Expected: All PASS

- [ ] **Step 3: Verify production build**

Run: `cd /Users/khxsh/Documents/repos/vault-agent/.worktrees/taxonomy/ui && bun run build`
Expected: Build succeeds

---

## Verification Summary
1. Backend tests: image filtering works, existing tests unbroken
2. Frontend tests: new layout renders, context menu appears on right-click, stats visible
3. Production build succeeds
4. Visual: page fills viewport, no sidebar, right-click shows context menu
