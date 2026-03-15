import logging
import re
from collections import Counter
from pathlib import PurePosixPath

import frontmatter

from src.models import VaultNote, VaultNoteSummary, VaultMap
from src.vault import validate_path, iter_markdown_files

logger = logging.getLogger("vault-agent")

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


# Parse YAML frontmatter from raw markdown, returning metadata dict and body content.
def parse_frontmatter(raw: str) -> tuple[dict, str]:
    try:
        post = frontmatter.loads(raw)
        return dict(post.metadata), post.content
    except Exception as e:
        logger.debug("Failed to parse frontmatter: %s", e)
        return {}, raw


# Extract deduplicated [[wikilink]] targets from markdown content, preserving order.
def extract_wikilinks(content: str) -> list[str]:
    links = [m.group(1) for m in WIKILINK_RE.finditer(content)]
    return list(dict.fromkeys(links))  # dedupe preserving order


# Extract all heading texts (h1-h6) from markdown content.
def extract_headings(content: str) -> list[str]:
    return [m.group(2) for m in HEADING_RE.finditer(content)]


# Parse a markdown file into a lightweight summary with title, wikilinks, and headings.
#
# Args:
#     file_path: Relative path from vault root (forward slashes).
#     raw: Raw file content including frontmatter.
#
# Returns:
#     VaultNoteSummary with extracted metadata.
def parse_note_summary(file_path: str, raw: str) -> VaultNoteSummary:
    fm, content = parse_frontmatter(raw)

    title = fm.get("title") if isinstance(fm.get("title"), str) else None
    if not title:
        title = PurePosixPath(file_path).stem

    return VaultNoteSummary(
        path=file_path,
        title=title,
        wikilinks=extract_wikilinks(content),
        headings=extract_headings(content),
    )


# Produce a vault summary with folder tree, note titles, and top headings.
#
# For vaults with <=200 notes, lists each note with its headings so the agent
# can discover relevant notes without semantic search. For larger vaults,
# shows only the folder tree with note counts.
#
# Args:
#     summaries: List of all note summaries in the vault.
#
# Returns:
#     Formatted string with folder structure and note listings.
def format_vault_summary(summaries: list[VaultNoteSummary]) -> str:
    total = len(summaries)

    folder_counts: Counter[str] = Counter()
    for note in summaries:
        folder = str(PurePosixPath(note.path).parent)
        folder_counts[folder] += 1

    folder_lines: list[str] = []
    for folder in sorted(folder_counts):
        label = "Root" if folder == "." else folder
        folder_lines.append(f"  {label}/ ({folder_counts[folder]} notes)")

    lines = [
        f"## Vault Summary ({total} notes)",
        "",
        "### Folder Structure",
        *folder_lines,
        "",
    ]

    if total > 200:
        lines.append("Large vault — use `read_note` with a specific path.")
    else:
        lines.append("### Notes")
        for note in summaries:
            entry = f"- `{note.path}` — {note.title}"
            if note.headings:
                h_list = ", ".join(note.headings[:5])
                entry += f" [h: {h_list}]"
            lines.append(entry)
        lines.append("")
        lines.append("Use `read_note` to inspect specific notes by path.")

    return "\n".join(lines)


# Scan the entire vault and build a VaultMap with note summaries and a compact string.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#
# Returns:
#     VaultMap with total count, per-note summaries, and formatted string.
def build_vault_map(vault_path: str) -> VaultMap:
    summaries: list[VaultNoteSummary] = []

    for md_file, file_path in iter_markdown_files(vault_path):
        raw = md_file.read_text(encoding="utf-8")
        summaries.append(parse_note_summary(file_path, raw))

    total_notes = len(summaries)
    as_string = format_vault_summary(summaries)

    return VaultMap(total_notes=total_notes, notes=summaries, as_string=as_string)


# Read a single note from the vault and parse its frontmatter and wikilinks.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     note_path: Relative path to the note from vault root.
#
# Returns:
#     VaultNote with parsed frontmatter, content, and wikilinks.
#
# Raises:
#     FileNotFoundError: When note_path does not exist on disk.
def read_note(vault_path: str, note_path: str) -> VaultNote:
    full_path = validate_path(vault_path, note_path)

    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")

    raw = full_path.read_text(encoding="utf-8")
    fm, content = parse_frontmatter(raw)

    return VaultNote(
        path=note_path,
        frontmatter=fm,
        content=content,
        wikilinks=extract_wikilinks(content),
    )
