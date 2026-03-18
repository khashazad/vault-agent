from src.models import TaxonomyProposal, TagNode


# Render a tag hierarchy as an indented markdown list string.
#
# Args:
#     nodes: List of TagNode trees to render.
#     indent: Current indentation level (2 spaces per level).
#
# Returns:
#     Formatted string with one tag per line.
def _format_tag_tree(nodes: list[TagNode], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    for node in nodes:
        desc = f" — {node.description}" if node.description else ""
        lines.append(f"{prefix}- {node.name}{desc}")
        if node.children:
            lines.append(_format_tag_tree(node.children, indent + 1))
    return "\n".join(lines)


# Build the (system, user) prompt pair for migrating a single note.
#
# The system prompt contains the full taxonomy (folders, tags, link targets)
# and migration rules. The user prompt contains the note content and path.
#
# Args:
#     taxonomy: Active taxonomy with folders, tags, and link targets.
#     note_content: Raw markdown content of the note to migrate.
#     note_path: Current relative path of the note in the vault.
#
# Returns:
#     Tuple of (system_prompt, user_prompt) strings.
def build_migration_prompt(
    taxonomy: TaxonomyProposal,
    note_content: str,
    note_path: str,
) -> tuple[str, str]:
    folders_str = "\n".join(f"- {f}" for f in taxonomy.folders)
    tags_str = _format_tag_tree(taxonomy.tag_hierarchy)

    link_lines: list[str] = []
    for lt in taxonomy.link_targets:
        aliases = ", ".join(lt.aliases) if lt.aliases else "none"
        link_lines.append(f"- [[{lt.title}]] (aliases: {aliases}) → {lt.folder}")
    links_str = "\n".join(link_lines)

    system = f"""You are an Obsidian vault migration assistant. Your job is to migrate a single note into a standardized format using the curated taxonomy below.

## Migration Rules

1. **Folder assignment**: Assign this note to the most appropriate folder from the taxonomy.
2. **Frontmatter**: Standardize to YAML with `tags` (plural array from taxonomy), `created` (YYYY-MM-DD), and any existing metadata worth preserving.
3. **Tags**: Use ONLY tags from the taxonomy hierarchy. Pick the most specific applicable tags.
4. **Wikilinks**: Add [[wikilinks]] to canonical link targets wherever they are mentioned in the text. Use the title form, not aliases. Only link the first occurrence of each target.
5. **Callouts**: Convert any admonition/list callout syntax to Obsidian-native `> [!type]` callouts. Valid types: note, warning, tip, important, caution, example, quote, abstract, info, todo, success, failure, bug, danger, question.
6. **Headings**: Standardize heading hierarchy (h1 = note title, h2+ for sections). Remove redundant or empty headings.
7. **Formatting**: Light cleanup — fix broken markdown, remove redundant whitespace, standardize list markers. PRESERVE all prose meaning and content.
8. **Math**: Keep LaTeX math (`$...$` or `$$...$$`) intact.
9. **Code blocks**: Keep code blocks intact.
10. **Embeds and block refs**: Keep `![[...]]` embeds and `^block-id` references intact.
11. **New link targets**: If the note mentions concepts that SHOULD be link targets but aren't in the taxonomy, list them at the end in a special section.

## Curated Taxonomy

### Folders
{folders_str}

### Tag Hierarchy
{tags_str}

### Link Targets
{links_str}

## Output Format

Return ONLY the complete migrated markdown note. At the very end, after the note content, add a section:

<!-- MIGRATION_META
target_folder: <folder path from taxonomy>
new_link_targets: <comma-separated list of suggested new link targets, or "none">
-->

This metadata block will be parsed programmatically — do not alter its format."""

    user = f"""## Note to Migrate

**Current path:** `{note_path}`

**Content:**
{note_content}

Migrate this note following all migration rules. Return ONLY the migrated markdown with the MIGRATION_META block at the end."""

    return system, user
