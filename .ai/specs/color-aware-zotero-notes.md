# Color-Aware Zotero Paper Note Generation

## Why

Zotero annotation colors carry semantic meaning (green=general, yellow=important, red=critical) but are **dropped** in `_paper_to_content_items()`. The agent also lacks vault-specific paper note formatting instructions, producing generic output instead of matching the vault's established `ad-callout`, `- !` emphasis, and structured paper summary conventions.

## What

Thread annotation color from Zotero through ContentItem into the agent prompt, and add a Zotero-specific system prompt that instructs Claude to generate structured paper summary notes matching the vault's format with color-driven importance levels.

## Context

**Relevant files:**
- `src/models/content.py` — ContentItem model, needs `color` field
- `src/zotero/orchestrator.py` — `_paper_to_content_items()` drops `ann.color`
- `src/zotero/client.py` — `ZoteroAnnotation.color` already has hex codes
- `src/agent/prompts.py` — system/user prompt builder, needs Zotero template + color labels
- `src/agent/agent.py` — `_init_agent()` calls `build_system_prompt()`, needs to pass `source_type`
- `ui/src/types.ts` — TS ContentItem interface, needs `color` field

**Patterns to follow:**
- `SOURCE_CONFIGS` dict pattern in `prompts.py` for per-source customization
- Optional fields with `Field(default=None)` in pydantic models (see `annotation` field)

**Key decisions:**
- `color` goes on ContentItem (per-annotation), not SourceMetadata (per-paper)
- Hex→semantic label mapping lives in `prompts.py` (prompt-facing logic)
- Zotero template replaces generic "New Note Template" section conditionally
- Agent sees "Critical"/"Important"/"General" labels, never raw hex codes
- Color informs **synthesis weighting**, not output formatting — red annotations get more prominence in the note, but formatting is uniform vault style
- Citekey in aliases uses Zotero item key (e.g. `Paper - ABC123XY`)

## Constraints

**Must:**
- Follow vault conventions: `ad-type` callouts, `- !` emphasis, `$\large{...}$` math, frontmatter with `created`/`aliases`/`tags`, `[[wikilinks]]`
- Not break web/book highlight flows (color defaults to None)

**Must not:**
- Change tool definitions, changeset/diff logic, or API routes
- Add new dependencies

**Out of scope:**
- UI color badge rendering on changeset review
- Configurable color→semantic mappings
- Changes to web/book highlight prompts

## Tasks

### T1: Data model + color threading

**Do:**
1. Add `color: str | None = Field(default=None, max_length=20)` to `ContentItem` in `src/models/content.py`
2. Pass `ann.color or None` in `_paper_to_content_items()` in `src/zotero/orchestrator.py`
3. Add `color?: string` to `ContentItem` interface in `ui/src/types.ts`

**Files:** `src/models/content.py`, `src/zotero/orchestrator.py`, `ui/src/types.ts`

**Verify:** `uv run python -c "from src.models.content import ContentItem; c = ContentItem(text='t', source='s', color='#ff6666'); print(c.color)"` prints `#ff6666`

### T2: Zotero-specific system prompt + color labels in user message

**Do:**
1. Add `COLOR_SEMANTICS` dict and `get_color_label()` function to `src/agent/prompts.py`
2. Add `ZOTERO_PAPER_TEMPLATE` constant with vault paper summary format: frontmatter (`created`/`aliases`/`tags` with Zotero item key as citekey), heading structure, `ad-type` callouts, `- !`/`- =` bullets, `$\large{...}$` math, `[[wikilinks]]`, and annotation priority guidance (color = synthesis weighting, not output formatting — critical annotations must appear prominently, general ones used selectively)
3. Modify `build_system_prompt()` to accept `source_type: str = "web"` param; conditionally inject `ZOTERO_PAPER_TEMPLATE` instead of generic template when `source_type == "zotero"`
4. Modify `build_batch_user_message()` and `build_user_message()` to include `**Priority:** {label}` per annotation when `item.color` is set
5. Thread `source_type=items[0].source_type` through `build_system_prompt()` call in `src/agent/agent.py`

**Files:** `src/agent/prompts.py`, `src/agent/agent.py`

**Verify:** Manual — sync a Zotero paper with colored annotations, inspect the generated changeset. Note should follow vault paper template with color-aware priority formatting.

**Color mapping (incoming annotation importance — affects synthesis weighting, not output formatting):**
| Hex | Label | Synthesis guidance |
|-----|-------|--------------------|
| `#ff6666` (Red) | Critical | Must appear in note, feature prominently |
| `#ffd400` (Yellow) | Important | Should appear in note, key supporting content |
| `#5fb236` (Green) | General | Include selectively, background/context |

Only these three colors are mapped. Any other color has no priority label attached.

## Done

- [ ] `uv run python -c "from src.models.content import ContentItem; ContentItem(text='t', source='s', color='#ff6666')"` succeeds
- [ ] `cd ui && bun run build` succeeds (TS types valid)
- [ ] Manual: sync a Zotero paper → changeset note uses vault paper template (ad-callouts, `- !` bullets, frontmatter with `created`/`aliases`/`tags`)
- [ ] Manual: red annotations appear as Critical priority, yellow as Important, green as General in agent's user message
- [ ] Manual: existing web highlight preview still works (no regression)
