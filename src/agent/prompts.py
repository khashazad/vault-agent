from src.models.content import ContentItem, SourceMetadata

_MAX_TITLE_LENGTH = 300
_MAX_AUTHOR_LENGTH = 100
_MAX_DOI_LENGTH = 100

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


ZOTERO_PAPER_TEMPLATE = """## Paper Note Template

When creating a note for a Zotero paper, use this structure:

---
created: YYYY-MM-DD
aliases:
  - "Paper - {ZOTERO_ITEM_KEY}"
tags:
  - paper
---

# Paper Title

Brief synthesis of the paper's core contribution and why it matters.

## Key Findings

- Synthesized critical findings in analytical voice
- Important methodology or approach details
- Key implications and connections to broader themes

## Detailed Notes

### Subtopic Heading

Analytical summary synthesized from annotations. Use standard blockquotes
sparingly — at most 2-3 essential passages across the entire note.

## References

- DOI / URL if available

### Synthesis guidelines
- Write a detailed analytical summary in your own voice. The note serves as a
  paper refresher — the reader should understand the paper's contributions
  without returning to the original.
- At most 2-3 direct quotes (standard > blockquote) for passages that are
  definitional or particularly well-phrased. Everything else: synthesize.
- No callout syntax (no > [!...]), no custom emphasis bullet markers.
  Plain markdown only.
- Use [[wikilinks]] to connect to existing vault notes where relevant.
- When the paper's findings rely on specific equations or the annotation
  highlights a critical formula, include it using LaTeX math (`$...$` or
  `$$...$$`). Do not use math formatting for emphasis or definitions —
  only for actual mathematical expressions from the paper.
- Code and implementation details: only include if the reader's annotation
  specifically highlights them. Don't quote code blocks from the paper.
- Frontmatter must include created, aliases (with Zotero item key), and tags.

### Annotation priority guidance
Annotations have priority labels (Critical, Important, General) based on
highlight color:
- Critical: Must inform key findings and get prominent coverage
- Important: Should shape the detailed notes sections
- General: Use selectively for background — not everything needs inclusion
Priority informs synthesis weighting, not output formatting."""


# Build (system_prompt, user_message) for single-call Zotero note synthesis.
#
# No tools, no vault map, no routing -- just annotation -> markdown.
#
# Args:
#     items: Annotations to synthesize into a note.
#     metadata: Paper metadata for citations and context.
#     feedback: User feedback from a rejected previous attempt.
#     previous_reasoning: Agent reasoning from the rejected attempt.
#
# Returns:
#     Tuple of (system_prompt, user_message).
def build_zotero_synthesis_prompt(
    items: list[ContentItem],
    metadata: SourceMetadata,
    feedback: str | None = None,
    previous_reasoning: str | None = None,
    registry=None,
) -> tuple[str, str]:
    system = (
        "You are a research note synthesizer. Your job is to produce a detailed "
        "analytical summary of a paper based on the reader's annotations. "
        "Write in your own voice — synthesize, don't transcribe. "
        "The note should serve as a standalone paper refresher.\n\n"
        "Return ONLY the complete markdown note — no preamble, no explanation, "
        "no code fences.\n\n"
        f"{ZOTERO_PAPER_TEMPLATE}"
    )

    if registry:
        tags = registry.get_tag_hierarchy()
        link_targets = registry.get_link_targets()
        target_lines = [f"- [[{lt['title']}]]" for lt in link_targets]
        system += f"""

## Vault Taxonomy
Use these tags: {", ".join(tags)}
Link to these notes when mentioned:
{chr(10).join(target_lines)}
Place new notes in: Papers/"""

    user = _format_zotero_context(metadata) + "\n\n"
    user += f"## Annotations ({len(items)} total)\n\n"
    for i, item in enumerate(items, 1):
        label = get_color_label(item.color)
        prefix = f"[{label}] " if label else ""
        comment = f" — {item.annotation}" if item.annotation else ""
        user += f'{i}. {prefix}"{item.text}"{comment}\n'

    if feedback and previous_reasoning:
        user += "\n## Previous Attempt (rejected by user)\n\n"
        user += f"**Previous reasoning:**\n{previous_reasoning}\n\n"
        user += f"**User feedback:** {feedback}\n\n"
        user += "Please revise your note based on the user's feedback.\n\n"

    user += (
        "\nWrite a detailed analytical summary of this paper based on the "
        "annotations above. Follow the Paper Note Template. Synthesize in your "
        "own voice — quote at most 2-3 essential passages. Return ONLY the markdown."
    )
    return system, user


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
        lines.append(
            f"**Title:** {_sanitize_metadata(metadata.title, _MAX_TITLE_LENGTH)}"
        )
    if metadata.authors:
        first = _sanitize_metadata(metadata.authors[0], _MAX_AUTHOR_LENGTH)
        suffix = " et al." if len(metadata.authors) > 1 else ""
        lines.append(f"**Author:** {first}{suffix}")
    if metadata.year:
        lines.append(f"**Year:** {_sanitize_metadata(metadata.year, 10)}")
    if metadata.doi:
        lines.append(f"**DOI:** {_sanitize_metadata(metadata.doi, _MAX_DOI_LENGTH)}")
    return "\n".join(lines)
