import logging
import re
from collections import Counter
from pathlib import Path, PurePosixPath

import frontmatter

from src.models import VaultNote, VaultNoteSummary, VaultMap
from src.vault import validate_path

logger = logging.getLogger("vault-agent")

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
INLINE_TAG_RE = re.compile(
    r"(?<=\s)#([a-zA-Z][\w/-]*)|^#([a-zA-Z][\w/-]*)", re.MULTILINE
)


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    try:
        post = frontmatter.loads(raw)
        return dict(post.metadata), post.content
    except Exception as e:
        logger.debug("Failed to parse frontmatter: %s", e)
        return {}, raw


def extract_wikilinks(content: str) -> list[str]:
    links = [m.group(1) for m in WIKILINK_RE.finditer(content)]
    return list(dict.fromkeys(links))  # dedupe preserving order


def extract_headings(content: str) -> list[str]:
    return [m.group(2) for m in HEADING_RE.finditer(content)]


def extract_tags(fm: dict, content: str) -> list[str]:
    tags: list[str] = []

    fm_tags = fm.get("tags")
    if isinstance(fm_tags, list):
        for t in fm_tags:
            if isinstance(t, str):
                tags.append(t)

    for m in INLINE_TAG_RE.finditer(content):
        tag = m.group(1) or m.group(2)
        if tag:
            tags.append(tag)

    return list(dict.fromkeys(tags))


def parse_note_summary(file_path: str, raw: str) -> VaultNoteSummary:
    fm, content = _parse_frontmatter(raw)

    title = fm.get("title") if isinstance(fm.get("title"), str) else None
    if not title:
        title = PurePosixPath(file_path).stem

    return VaultNoteSummary(
        path=file_path,
        title=title,
        tags=extract_tags(fm, content),
        wikilinks=extract_wikilinks(content),
        headings=extract_headings(content),
    )


def format_compact_vault_summary(summaries: list[VaultNoteSummary]) -> str:
    """Produce a compact vault summary (~500-800 tokens) with folder tree,
    top tags, and total note count. Used when RAG is enabled so the agent
    relies on search_vault for discovery instead of a full listing."""

    total = len(summaries)

    # Folder tree with note counts
    folder_counts: Counter[str] = Counter()
    for note in summaries:
        folder = str(PurePosixPath(note.path).parent)
        folder_counts[folder] += 1

    folder_lines: list[str] = []
    for folder in sorted(folder_counts):
        label = "Root" if folder == "." else folder
        folder_lines.append(f"  {label}/ ({folder_counts[folder]} notes)")

    # Top 30 tags by frequency
    tag_counter: Counter[str] = Counter()
    for note in summaries:
        for tag in note.tags:
            tag_counter[tag] += 1

    top_tags = [tag for tag, _ in tag_counter.most_common(30)]

    lines = [
        f"## Vault Summary ({total} notes)",
        "",
        "### Folder Structure",
        *folder_lines,
        "",
    ]

    if top_tags:
        lines.append("### Top Tags")
        lines.append(", ".join(top_tags))
        lines.append("")

    lines.append(
        "Use `search_vault` to find notes by content. "
        "Use `read_note` to inspect specific notes by path."
    )

    return "\n".join(lines)


def build_vault_map(vault_path: str) -> VaultMap:
    vault = Path(vault_path)
    summaries: list[VaultNoteSummary] = []

    for md_file in vault.rglob("*.md"):
        rel = md_file.relative_to(vault)
        # Skip hidden directories/files (e.g. .obsidian/)
        if any(part.startswith(".") for part in rel.parts):
            continue

        raw = md_file.read_text(encoding="utf-8")
        file_path = str(PurePosixPath(rel))  # always forward slashes
        summaries.append(parse_note_summary(file_path, raw))

    total_notes = len(summaries)
    as_string = format_compact_vault_summary(summaries)

    return VaultMap(total_notes=total_notes, notes=summaries, as_string=as_string)


def read_note(vault_path: str, note_path: str) -> VaultNote:
    full_path = validate_path(vault_path, note_path)

    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")

    raw = full_path.read_text(encoding="utf-8")
    fm, content = _parse_frontmatter(raw)

    return VaultNote(
        path=note_path,
        frontmatter=fm,
        content=content,
        wikilinks=extract_wikilinks(content),
        tags=extract_tags(fm, content),
    )
