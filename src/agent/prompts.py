from src.models import HighlightInput

BASE_TOOL_DESCRIPTIONS = [
    "- **read_note**: Read the full content of a note. Always read a note before modifying it.",
    "- **create_note**: Create a new note when the highlight covers a topic not yet in the vault.",
    "- **update_note**: Add content to an existing note (append a section) or add tags to frontmatter.",
]

SEARCH_VAULT_TOOL_DESC = "- **search_vault**: Semantic search across note contents. Use this FIRST to find relevant notes before reading or creating."

BASE_RULES = [
    "ALWAYS read a note before modifying it. Never update a note you haven't read first.",
    "Before creating a new note, verify there is no existing note covering this topic. Prefer updating existing notes over creating new ones.",
    "Follow the vault's existing naming conventions and folder structure.",
    "Include proper YAML frontmatter with tags, source URL, and created date.",
    "Use [[wikilinks]] to connect the highlight to related notes that exist in the vault.",
    "Preserve the original highlight text faithfully — do not paraphrase the source material.",
    "Add brief contextual commentary to help the user understand relevance.",
    "Be concise. Integrate highlights, don't write essays.",
    "All operations are additive only. You cannot delete content or overwrite existing sections.",
]

SEARCH_VAULT_RULE = "ALWAYS start by using search_vault to find notes semantically related to the highlight topic. This searches note contents, not just titles."


def build_system_prompt(vault_map_string: str, rag_enabled: bool = False) -> str:
    tools = list(BASE_TOOL_DESCRIPTIONS)
    rules = list(BASE_RULES)

    if rag_enabled:
        tools.insert(0, SEARCH_VAULT_TOOL_DESC)
        rules.insert(0, SEARCH_VAULT_RULE)

    tools_section = "## Your Tools\n\n" + "\n".join(tools)
    rules_section = "## Rules\n\n" + "\n".join(
        f"{i}. {rule}" for i, rule in enumerate(rules, 1)
    )

    return f"""You are Vault Agent, an AI assistant that integrates web highlights into an Obsidian vault.

You have access to the user's Obsidian vault structure shown below. Your job is to decide where a highlight belongs and integrate it intelligently.

{vault_map_string}

{tools_section}

{rules_section}

## Obsidian Conventions

- Frontmatter: YAML block with `---`. Always use `tags` (plural array).
- Wikilinks: `[[Note Title]]`, `[[Note Title|display]]`, `[[Note Title#Heading]]`
- Tags: `#tag` inline or `tags: [tag1, tag2]` in frontmatter. Hierarchical: `#projects/vault-agent`
- Never modify callouts (`> [!note]`), dataview queries, embeds (`![[Note]]`), or block references (`^block-id`).

## New Note Template

```markdown
---
tags: []
source: ""
created: YYYY-MM-DD
---

# Note Title

Content with [[wikilinks]] to related notes.

## Source Highlights

> Highlighted text

Commentary about the highlight.
```"""


def build_user_message(highlight: HighlightInput) -> str:
    msg = "Please integrate this highlight into my vault:\n\n"
    msg += f"**Highlighted text:**\n> {highlight.text}\n\n"
    msg += f"**Source:** {highlight.source}\n"
    if highlight.annotation:
        msg += f"**My note:** {highlight.annotation}\n"
    if highlight.tags and len(highlight.tags) > 0:
        msg += f"**Suggested tags:** {', '.join(highlight.tags)}\n"
    return msg
