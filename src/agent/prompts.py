from dataclasses import dataclass

from src.models.content import ContentItem, SourceMetadata


COLOR_SEMANTICS: dict[str, str] = {
    "#ff6666": "Critical",
    "#ffd400": "Important",
    "#5fb236": "General",
}


# Map a hex color code to a semantic priority label.
#
# Args:
#     color: Hex color string (e.g. "#ff6666").
#
# Returns:
#     Priority label ("Critical", "Important", "General") or None if no match.
def get_color_label(color: str | None) -> str | None:
    if not color:
        return None
    return COLOR_SEMANTICS.get(color.lower())


# Source-type-specific terminology and role description for prompt templates.
@dataclass
class SourceConfig:
    singular: str
    plural: str
    role_desc: str


SOURCE_CONFIGS: dict[str, SourceConfig] = {
    "web": SourceConfig(
        "highlight", "highlights", "integrates web content into an Obsidian vault"
    ),
    "zotero": SourceConfig(
        "annotation",
        "annotations",
        "integrates research paper annotations into an Obsidian vault",
    ),
    "book": SourceConfig(
        "highlight", "highlights", "integrates book highlights into an Obsidian vault"
    ),
}

BASE_TOOL_DESCRIPTIONS = [
    "- **read_note**: Read the full content of a note. Always read a note before modifying it.",
    "- **create_note**: Create a new note when the {singular} covers a topic not yet in the vault.",
    "- **update_note**: Add content to an existing note (append a section).",
]

SEARCH_VAULT_TOOL_DESC = "- **search_vault**: Semantic search across note contents. Use this FIRST to find relevant notes before reading or creating."

REPORT_ROUTING_TOOL_DESC = "- **report_routing_decision**: Declare your placement decision (update, create, or skip if already in vault). Call this exactly ONCE before making changes."

ROUTING_GUIDANCE = """## Routing Instructions

Before making any changes, you MUST decide where this {singular} belongs:

1. **Review search results**: Review the search results provided below. If they are insufficient, use `search_vault` for additional searches.
2. **Read candidates**: Read 1-3 of the most promising notes to inspect their content and structure.
3. **Report your decision**: Call `report_routing_decision` with your placement choice:
   - **action**: "update" if the {singular} fits an existing note, "create" if it needs a new one, "skip" if the information is already adequately covered in the vault.
   - **target_path**: The path of the note to update, or the suggested path for a new note. Not needed for skip.
   - **reasoning**: Brief explanation of why this placement was chosen (1-2 sentences). For skip, explain what existing content already covers this {singular}.
   - **confidence**: 0.8+ for strong matches, 0.5-0.8 for reasonable, below 0.5 for uncertain.
   - **duplicate_notes**: When action="skip", list the paths of notes that already contain this information.
4. **Execute changes**: After reporting your decision, use create_note or update_note to integrate the {singular}. If you chose skip, do NOT call create_note or update_note — summarize your reasoning and finish.

You MUST call report_routing_decision before any create_note or update_note calls."""

BASE_RULES = [
    "ALWAYS read a note before modifying it. Never update a note you haven't read first.",
    "Before creating a new note, verify there is no existing note covering this topic. Prefer updating existing notes over creating new ones.",
    "Follow the vault's existing naming conventions and folder structure.",
    "Include proper YAML frontmatter with source URL and created date.",
    "Use [[wikilinks]] to connect the {singular} to related notes that exist in the vault.",
    "Preserve the original {singular} text faithfully — do not paraphrase the source material.",
    "Add brief contextual commentary to help the user understand relevance.",
    "Be concise. Integrate {plural}, don't write essays.",
    "All operations are additive only. You cannot delete content or overwrite existing sections.",
]

SEARCH_VAULT_RULE = "ALWAYS start by using search_vault to find notes semantically related to the {singular} topic. The vault context above is a summary only (folder structure and tags) — search_vault searches actual note contents and is the primary way to discover relevant notes."

BATCH_ROUTING_GUIDANCE = """## Batch Processing Instructions

You are receiving multiple {plural} at once. Your job is to integrate them coherently:

1. **Review search results**: Review the search results provided below. If they are insufficient, use `search_vault` for additional searches.
2. **Read candidates**: Read promising notes to understand existing coverage.
3. **Report routing**: Call `report_routing_decision` with your overall placement strategy. Use "skip" if all {plural} are already adequately covered in the vault.
4. **Execute coherently**: Create or update notes that weave the {plural} together logically. If you chose skip, do NOT make any changes — summarize and finish.
   - Prefer creating one well-structured note over many fragmented updates.
   - Group {plural} by subtopic under appropriate headings.
   - Preserve each {singular}'s original text faithfully as blockquotes.
   - Add connective commentary between {plural} where helpful.
   - Use the {singular} ordering as a guide — they often follow the source document's structure."""


ZOTERO_PAPER_TEMPLATE = """## Paper Note Template

When creating a note for a Zotero paper, use this structure:

```markdown
---
created: YYYY-MM-DD
aliases:
  - "Paper - {ZOTERO_ITEM_KEY}"
tags:
  - paper
---

# Paper Title

> [!ad-abstract]
> Brief synthesis of the paper's key contributions based on the annotations.

## Key Findings

- Critical findings from the annotations
- Important supporting points
- General context and background details

## Detailed Notes

### Subtopic Heading

> Quoted annotation text

Commentary linking this to broader themes.

## References

- DOI / URL if available
```

### Formatting conventions
- **Callouts**: Use `> [!ad-abstract]` for paper summaries, `> [!ad-quote]` for key quotes
- **Emphasis bullets**: `- !` for critical points, `- =` for notable points, plain `-` for general
- **Math**: Use `$\\large{...}$` for important terms or definitions
- **Links**: Always use `[[wikilinks]]` to connect to existing vault notes
- **Frontmatter**: Must include `created`, `aliases` (with Zotero item key as citekey), and `tags`

### Annotation priority guidance
Annotations have priority labels (Critical, Important, General) based on the reader's color coding:
- **Critical**: Must appear in the note and feature prominently in key findings
- **Important**: Should appear in the note as key supporting content
- **General**: Include selectively for background and context — not everything needs to be in the note

Priority informs **synthesis weighting**, not output formatting. All content uses the same formatting conventions above. Critical annotations simply get more prominence in the note structure."""


# Build (system_prompt, user_message) for single-call Zotero note synthesis.
#
# No tools, no vault map, no routing -- just annotation -> markdown.
#
# Args:
#     items: Annotations to synthesize into a note.
#     metadata: Paper metadata for citations and context.
#
# Returns:
#     Tuple of (system_prompt, user_message).
def build_zotero_synthesis_prompt(
    items: list[ContentItem],
    metadata: "SourceMetadata",
) -> tuple[str, str]:
    system = (
        "You are a research note synthesizer. Your job is to transform paper "
        "annotations into a well-structured Obsidian markdown note.\n\n"
        "Return ONLY the complete markdown note — no preamble, no explanation, "
        "no code fences.\n\n"
        f"{ZOTERO_PAPER_TEMPLATE}"
    )

    user = _format_zotero_context(metadata) + "\n\n"
    user += f"## Annotations ({len(items)} total)\n\n"
    for i, item in enumerate(items, 1):
        label = get_color_label(item.color)
        prefix = f"[{label}] " if label else ""
        comment = f" — {item.annotation}" if item.annotation else ""
        user += f'{i}. {prefix}"{item.text}"{comment}\n'

    user += (
        "\nSynthesize these annotations into a single Obsidian note following "
        "the Paper Note Template above. Return ONLY the markdown."
    )
    return system, user


# Format a template string with source config singular/plural terms.
def _fmt(template: str, sc: SourceConfig) -> str:
    return template.format(singular=sc.singular, plural=sc.plural)


# Build the full system prompt for the agent, including vault map, tools, rules, and templates.
#
# Args:
#     vault_map_string: Rendered vault structure string for LLM context.
#     source_config: Source-type terminology config.
#     is_batch: Whether this is a batch processing run.
#     source_type: Content source type ("web", "zotero", "book").
#
# Returns:
#     Complete system prompt string.
def build_system_prompt(
    vault_map_string: str,
    source_config: SourceConfig,
    is_batch: bool = False,
    source_type: str = "web",
) -> str:
    sc = source_config
    tools = [_fmt(t, sc) for t in BASE_TOOL_DESCRIPTIONS]
    tools.insert(0, REPORT_ROUTING_TOOL_DESC)
    tools.insert(0, SEARCH_VAULT_TOOL_DESC)
    rules = [_fmt(r, sc) for r in BASE_RULES]
    rules.insert(0, _fmt(SEARCH_VAULT_RULE, sc))

    tools_section = "## Your Tools\n\n" + "\n".join(tools)
    rules_section = "## Rules\n\n" + "\n".join(
        f"{i}. {rule}" for i, rule in enumerate(rules, 1)
    )

    batch_section = f"\n\n{_fmt(BATCH_ROUTING_GUIDANCE, sc)}" if is_batch else ""

    if source_type == "zotero":
        note_template = ZOTERO_PAPER_TEMPLATE
    else:
        note_template = f"""## New Note Template

```markdown
---
source: ""
created: YYYY-MM-DD
---

# Note Title

Content with [[wikilinks]] to related notes.

## Source {sc.plural.title()}

> {sc.singular.title()} text

Commentary about the {sc.singular}.
```"""

    return f"""You are Vault Agent, an AI assistant that {sc.role_desc}.

You have access to the user's Obsidian vault structure shown below. Your job is to decide where {"these " + sc.plural + " belong" if is_batch else "a " + sc.singular + " belongs"} and integrate {"them" if is_batch else "it"} intelligently.

{vault_map_string}

{tools_section}

{_fmt(ROUTING_GUIDANCE, sc)}{batch_section}

{rules_section}

## Obsidian Conventions

- Frontmatter: YAML block with `---`.
- Wikilinks: `[[Note Title]]`, `[[Note Title|display]]`, `[[Note Title#Heading]]`
- Never modify callouts (`> [!note]`), dataview queries, embeds (`![[Note]]`), or block references (`^block-id`).

{note_template}"""


# Build the user message for a single content item integration request.
#
# Args:
#     item: The content item to integrate.
#     source_config: Source-type terminology config.
#     feedback: User feedback from a rejected previous attempt.
#     previous_reasoning: Agent reasoning from the rejected attempt.
#     search_context: Pre-fetched vault search results to include.
#
# Returns:
#     Formatted user message string.
def build_user_message(
    item: ContentItem,
    source_config: SourceConfig,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    search_context: str | None = None,
) -> str:
    sc = source_config
    msg = f"Please integrate this {sc.singular} into my vault:\n\n"
    msg += f"**{sc.singular.title()} text:**\n> {item.text}\n\n"
    msg += f"**Source:** {item.source}\n"
    if item.annotation:
        msg += f"**My note:** {item.annotation}\n"
    label = get_color_label(item.color)
    if label:
        msg += f"**Priority:** {label}\n"
    if feedback and previous_reasoning:
        msg += "\n## Previous Attempt (rejected by user)\n\n"
        msg += f"**Previous reasoning:**\n{previous_reasoning}\n\n"
        msg += f"**User feedback:** {feedback}\n\n"
        msg += "Please reconsider your approach based on the user's feedback. "
        msg += "Search again if needed, then make a new routing decision and generate changes.\n"

    if search_context:
        msg += "\n## Vault Search Results\n\n"
        msg += (
            f"The following notes are semantically related to this {sc.singular}:\n\n"
        )
        msg += search_context
        msg += "\n\nUse `read_note` to inspect any of these before making changes.\n"

    return msg


# Sanitize a metadata string by stripping newlines and truncating.
#
# Args:
#     value: Raw metadata string.
#     max_length: Maximum character length.
#
# Returns:
#     Cleaned, truncated string.
def _sanitize_metadata(value: str, max_length: int = 500) -> str:
    sanitized = value.replace("\n", " ").replace("\r", " ")
    return sanitized[:max_length].strip()


# Format source metadata into a markdown block for agent context.
#
# Args:
#     metadata: Source metadata to format.
#     source_type: Content source type; only "zotero" produces output.
#
# Returns:
#     Markdown string, or empty string for non-Zotero sources.
def _format_source_context(metadata: SourceMetadata, source_type: str) -> str:
    if source_type == "zotero":
        return _format_zotero_context(metadata)
    return ""


# Format Zotero paper metadata into a markdown block for agent context.
#
# Args:
#     metadata: Paper metadata (title, authors, DOI, etc.).
#
# Returns:
#     Markdown string with paper context section.
def _format_zotero_context(metadata: SourceMetadata) -> str:
    lines = ["## Paper Context\n"]
    if metadata.title:
        lines.append(f"**Title:** {_sanitize_metadata(metadata.title, 300)}")
    if metadata.authors:
        first = _sanitize_metadata(metadata.authors[0], 100)
        suffix = " et al." if len(metadata.authors) > 1 else ""
        lines.append(f"**Author:** {first}{suffix}")
    if metadata.year:
        lines.append(f"**Year:** {_sanitize_metadata(metadata.year, 10)}")
    if metadata.doi:
        lines.append(f"**DOI:** {_sanitize_metadata(metadata.doi, 100)}")
    return "\n".join(lines)


# Build the user message for a batch of content items.
#
# Falls back to build_user_message for single items without metadata.
#
# Args:
#     items: Content items to integrate.
#     source_config: Source-type terminology config.
#     feedback: User feedback from a rejected previous attempt.
#     previous_reasoning: Agent reasoning from the rejected attempt.
#     search_context: Pre-fetched vault search results to include.
#
# Returns:
#     Formatted user message string.
def build_batch_user_message(
    items: list[ContentItem],
    source_config: SourceConfig,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    search_context: str | None = None,
) -> str:
    sc = source_config

    if len(items) == 1 and not items[0].source_metadata:
        return build_user_message(
            items[0], source_config, feedback, previous_reasoning, search_context
        )

    sources = list(dict.fromkeys(item.source for item in items))
    source_str = ", ".join(sources) if len(sources) <= 3 else f"{len(sources)} sources"

    source_metadata = items[0].source_metadata

    if source_metadata:
        msg = f"Please integrate these {len(items)} {sc.plural} from a research paper into my vault.\n"
        msg += f"Sources: {source_str}\n\n"
        msg += _format_source_context(source_metadata, items[0].source_type) + "\n\n"
        msg += (
            f"Integrate these {sc.plural} coherently — create a well-structured note "
            f"for this paper rather than treating each {sc.singular} independently. "
            "Group related content together.\n\n"
        )
    else:
        msg = f"Please integrate these {len(items)} {sc.plural} into my vault.\n"
        msg += f"Sources: {source_str}\n\n"
        msg += (
            f"Integrate them coherently — create well-structured notes rather than "
            f"treating each {sc.singular} independently. Group related content together.\n\n"
        )

    for i, item in enumerate(items, 1):
        msg += f"### {sc.singular.title()} {i}\n"
        msg += f"**Text:**\n> {item.text}\n\n"
        msg += f"**Source:** {item.source}\n"
        if item.annotation:
            msg += f"**Note:** {item.annotation}\n"
        label = get_color_label(item.color)
        if label:
            msg += f"**Priority:** {label}\n"
        msg += "\n"

    if feedback and previous_reasoning:
        msg += "## Previous Attempt (rejected by user)\n\n"
        msg += f"**Previous reasoning:**\n{previous_reasoning}\n\n"
        msg += f"**User feedback:** {feedback}\n\n"
        msg += "Please reconsider your approach based on the user's feedback.\n"

    if search_context:
        msg += "## Vault Search Results\n\n"
        msg += f"The following notes are semantically related to these {sc.plural}:\n\n"
        msg += search_context
        msg += "\n\nUse `read_note` to inspect any of these before making changes.\n"

    return msg
