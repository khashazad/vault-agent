# Auto-Link Wikilinks in Generated Content

## Why

The LLM is instructed to use `[[wikilinks]]` but only sees a compact folder summary — it misses many linkable mentions. A post-processing pass over generated content can catch note-title mentions the LLM missed and wrap them in wikilinks, producing better-connected Obsidian notes with zero extra LLM cost.

## What

A `wikify()` function that scans proposed changeset content for mentions of existing vault note titles and wraps them in `[[wikilinks]]`. Called after content generation, before diff computation, in both changeset paths (agent loop + Zotero synthesis).

## Context

**Relevant files:**
- `src/agent/agent.py` — both changeset generation paths; hook point for wikify calls
- `src/vault/reader.py` — `build_vault_map()` already extracts titles + headings into `VaultNoteSummary`
- `src/vault/writer.py` — `compute_create()` / `compute_update()` produce content before diffing
- `src/models/vault.py` — `VaultMap`, `VaultNoteSummary` types (have `.title`, `.headings`, `.path`)

**Patterns to follow:**
- `src/vault/reader.py` regex patterns (`WIKILINK_RE`, `HEADING_RE`) for consistency
- `src/agent/diff.py` — small focused utility module pattern

**Key decisions:**
- **No new DB/index.** VaultMap already has all note titles in memory. Built fresh each agent run.
- **Include Headings as well**
- **First occurrence only.** Matches Obsidian convention — don't spam links.
- **Longest-match-first.** Prevents "Machine" matching before "Machine Learning".
- **Case-insensitive matching, canonical title in link.** `machine learning` → `[[Machine Learning]]`

## Constraints

**Must:**
- Skip frontmatter (`---` blocks), code blocks, inline code, existing wikilinks/embeds
- Skip self-links (don't link to the note being created/updated)
- Use word-boundary matching (`\b`) to avoid partial-word matches
- Filter out titles < 3 chars to avoid spurious matches
- Work in both `generate_changeset()` and `generate_zotero_note()` paths

**Must not:**
- Add new dependencies
- Modify VaultMap/VaultNoteSummary models
- Change the agent prompt or LLM behavior
- Touch the UI

**Out of scope:**
- Frontmatter alias matching — v2
- Fuzzy/semantic matching — v2
- Configuration/toggle for the feature

## Tasks

### T1: Create `src/agent/wikify.py`

**Do:**
- `_find_protected_spans(content: str) -> list[tuple[int, int]]` — returns sorted list of (start, end) spans that must not be modified:
  - Frontmatter (if content starts with `---\n`, find closing `---\n`)
  - Fenced code blocks (`` ```...``` ``)
  - Inline code (`` `...` ``)
  - Existing wikilinks and embeds (`!?[[...]]`)
  - Heading lines (`^#{1,6}\s+.*$`)
- `_overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool`
- `wikify(content: str, vault_map: VaultMap, self_path: str | None = None) -> str`:
  1. Build targets from `vault_map.notes` (exclude self_path, filter title len < 3, sort by len desc)
  2. Find protected spans
  3. For each target: regex `\b{escaped_title}\b` (IGNORECASE), find first non-protected match, collect `(start, end, f"[[{title}]]")`
  4. After claiming a match, add its span to protected list (prevents shorter titles overlapping)
  5. Sort all replacements by position, splice into content

**Files:** `src/agent/wikify.py` (new)

**Verify:** Unit tests — create test content with known note titles, verify correct linking, verify protected zones are respected

### T2: Integrate into changeset generation

**Do:**
- In `_init_agent()` (line 88): return `vault_map` as 5th tuple element
- In `generate_changeset()` (line 180): unpack `vault_map` from `_init_agent`
- After `compute_create()` (line 293): `proposed_content = wikify(proposed_content, vault_map, self_path=inp.path)`
- After `compute_update()` (line 321): `result = wikify(result, vault_map, self_path=inp.path)`
- In `generate_zotero_note()` (line 412): build vault_map via `build_vault_map(config.vault_path)`, call `wikify(note_content, vault_map, self_path=note_path)` before `generate_diff`

**Files:** `src/agent/agent.py`

**Verify:** Start server, trigger a Zotero sync for a paper, inspect the changeset diff — note titles that appear in the generated content should now be wrapped in `[[wikilinks]]`

## Done

- [ ] `uv run python -c "from src.agent.wikify import wikify; print('import ok')"` passes
- [ ] Manual: sync a Zotero paper, review changeset — generated content has auto-linked wikilinks to existing vault notes
- [ ] Manual: existing wikilinks in content are not double-wrapped
- [ ] Manual: frontmatter, code blocks, headings are untouched
- [ ] No regressions in existing changeset generation

## Unresolved

- Min title length: 3 chars excludes legit 2-char note titles ("AI", "ML"). Worth lowering to 2?
- Should `update_note` wikify only the appended section or full proposed content? Full content means existing text gets links added. Leaning toward full content since protected zones prevent double-linking.
