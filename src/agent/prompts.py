from src.models import HighlightInput

BASE_TOOL_DESCRIPTIONS = [
    "- **read_note**: Read the full content of a note. Always read a note before modifying it.",
    "- **create_note**: Create a new note when the highlight covers a topic not yet in the vault.",
    "- **update_note**: Add content to an existing note (append a section).",
]

SEARCH_VAULT_TOOL_DESC = "- **search_vault**: Semantic search across note contents. Use this FIRST to find relevant notes before reading or creating."

REPORT_ROUTING_TOOL_DESC = "- **report_routing_decision**: Declare your placement decision (update vs create, target path, reasoning, confidence). Call this exactly ONCE before making changes."

ROUTING_GUIDANCE = """## Routing Instructions

Before making any changes, you MUST decide where this highlight belongs:

1. **Review search results**: Review the search results provided below. If they are insufficient, use `search_vault` for additional searches.
2. **Read candidates**: Read 1-3 of the most promising notes to inspect their content and structure.
3. **Report your decision**: Call `report_routing_decision` with your placement choice:
   - **action**: "update" if the highlight fits an existing note, "create" if it needs a new one.
   - **target_path**: The path of the note to update, or the suggested path for a new note.
   - **reasoning**: Brief explanation of why this placement was chosen (1-2 sentences).
   - **confidence**: 0.8+ for strong matches, 0.5-0.8 for reasonable, below 0.5 for uncertain.
4. **Execute changes**: After reporting your decision, use create_note or update_note to integrate the highlight.

You MUST call report_routing_decision before any create_note or update_note calls."""

BASE_RULES = [
    "ALWAYS read a note before modifying it. Never update a note you haven't read first.",
    "Before creating a new note, verify there is no existing note covering this topic. Prefer updating existing notes over creating new ones.",
    "Follow the vault's existing naming conventions and folder structure.",
    "Include proper YAML frontmatter with source URL and created date.",
    "Use [[wikilinks]] to connect the highlight to related notes that exist in the vault.",
    "Preserve the original highlight text faithfully — do not paraphrase the source material.",
    "Add brief contextual commentary to help the user understand relevance.",
    "Be concise. Integrate highlights, don't write essays.",
    "All operations are additive only. You cannot delete content or overwrite existing sections.",
]

SEARCH_VAULT_RULE = "ALWAYS start by using search_vault to find notes semantically related to the highlight topic. The vault context above is a summary only (folder structure and tags) — search_vault searches actual note contents and is the primary way to discover relevant notes."

BATCH_ROUTING_GUIDANCE = """## Batch Processing Instructions

You are receiving multiple highlights at once. Your job is to integrate them coherently:

1. **Review search results**: Review the search results provided below. If they are insufficient, use `search_vault` for additional searches.
2. **Read candidates**: Read promising notes to understand existing coverage.
3. **Report routing**: Call `report_routing_decision` with your overall placement strategy.
4. **Execute coherently**: Create or update notes that weave the highlights together logically.
   - Prefer creating one well-structured note over many fragmented updates.
   - Group highlights by subtopic under appropriate headings.
   - Preserve each highlight's original text faithfully as blockquotes.
   - Add connective commentary between highlights where helpful.
   - Use the highlight ordering as a guide — they often follow the source document's structure."""


def build_system_prompt(vault_map_string: str, is_batch: bool = False) -> str:
    tools = list(BASE_TOOL_DESCRIPTIONS)
    tools.insert(0, REPORT_ROUTING_TOOL_DESC)
    tools.insert(0, SEARCH_VAULT_TOOL_DESC)
    rules = list(BASE_RULES)
    rules.insert(0, SEARCH_VAULT_RULE)

    tools_section = "## Your Tools\n\n" + "\n".join(tools)
    rules_section = "## Rules\n\n" + "\n".join(
        f"{i}. {rule}" for i, rule in enumerate(rules, 1)
    )

    batch_section = f"\n\n{BATCH_ROUTING_GUIDANCE}" if is_batch else ""

    return f"""You are Vault Agent, an AI assistant that integrates web highlights into an Obsidian vault.

You have access to the user's Obsidian vault structure shown below. Your job is to decide where {"these highlights belong" if is_batch else "a highlight belongs"} and integrate {"them" if is_batch else "it"} intelligently.

{vault_map_string}

{tools_section}

{ROUTING_GUIDANCE}{batch_section}

{rules_section}

## Obsidian Conventions

- Frontmatter: YAML block with `---`.
- Wikilinks: `[[Note Title]]`, `[[Note Title|display]]`, `[[Note Title#Heading]]`
- Never modify callouts (`> [!note]`), dataview queries, embeds (`![[Note]]`), or block references (`^block-id`).

## New Note Template

```markdown
---
source: ""
created: YYYY-MM-DD
---

# Note Title

Content with [[wikilinks]] to related notes.

## Source Highlights

> Highlighted text

Commentary about the highlight.
```"""


def build_user_message(
    highlight: HighlightInput,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    search_context: str | None = None,
) -> str:
    msg = "Please integrate this highlight into my vault:\n\n"
    msg += f"**Highlighted text:**\n> {highlight.text}\n\n"
    msg += f"**Source:** {highlight.source}\n"
    if highlight.annotation:
        msg += f"**My note:** {highlight.annotation}\n"
    if feedback and previous_reasoning:
        msg += "\n## Previous Attempt (rejected by user)\n\n"
        msg += f"**Previous reasoning:**\n{previous_reasoning}\n\n"
        msg += f"**User feedback:** {feedback}\n\n"
        msg += "Please reconsider your approach based on the user's feedback. "
        msg += "Search again if needed, then make a new routing decision and generate changes.\n"

    if search_context:
        msg += "\n## Vault Search Results\n\n"
        msg += "The following notes are semantically related to this highlight:\n\n"
        msg += search_context
        msg += "\n\nUse `read_note` to inspect any of these before making changes.\n"

    return msg


def build_batch_user_message(
    highlights: list[HighlightInput],
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    search_context: str | None = None,
) -> str:
    if len(highlights) == 1:
        return build_user_message(
            highlights[0], feedback, previous_reasoning, search_context
        )

    sources = list(dict.fromkeys(h.source for h in highlights))
    source_str = ", ".join(sources) if len(sources) <= 3 else f"{len(sources)} sources"

    msg = f"Please integrate these {len(highlights)} highlights into my vault.\n"
    msg += f"Sources: {source_str}\n\n"
    msg += (
        "Integrate them coherently — create well-structured notes rather than "
        "treating each highlight independently. Group related content together.\n\n"
    )

    for i, h in enumerate(highlights, 1):
        msg += f"### Highlight {i}\n"
        msg += f"**Text:**\n> {h.text}\n\n"
        msg += f"**Source:** {h.source}\n"
        if h.annotation:
            msg += f"**Note:** {h.annotation}\n"
        msg += "\n"

    if feedback and previous_reasoning:
        msg += "## Previous Attempt (rejected by user)\n\n"
        msg += f"**Previous reasoning:**\n{previous_reasoning}\n\n"
        msg += f"**User feedback:** {feedback}\n\n"
        msg += "Please reconsider your approach based on the user's feedback.\n"

    if search_context:
        msg += "## Vault Search Results\n\n"
        msg += "The following notes are semantically related to these highlights:\n\n"
        msg += search_context
        msg += "\n\nUse `read_note` to inspect any of these before making changes.\n"

    return msg
