import re

from src.models.vault import VaultMap

FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
WIKILINK_EMBED_RE = re.compile(r"!?\[\[[^\]]+\]\]")
HEADING_LINE_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)

_PROTECTED_PATTERNS = [
    FRONTMATTER_RE,
    FENCED_CODE_RE,
    INLINE_CODE_RE,
    WIKILINK_EMBED_RE,
    HEADING_LINE_RE,
]


# Collect character spans that must not be modified (frontmatter, code blocks,
# inline code, existing wikilinks/embeds, heading lines).
#
# Args:
#     content: Full markdown content string.
#
# Returns:
#     Sorted list of (start, end) tuples for protected spans.
def _find_protected_spans(content: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in _PROTECTED_PATTERNS:
        for m in pattern.finditer(content):
            spans.append((m.start(), m.end()))
    spans.sort(key=lambda s: s[0])
    return spans


# Check whether a candidate span overlaps any protected span.
#
# Args:
#     start: Start index of candidate span.
#     end: End index of candidate span.
#     spans: Sorted list of protected (start, end) tuples.
#
# Returns:
#     True if the candidate overlaps a protected span.
def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    for s, e in spans:
        if s >= end:
            break
        if e > start:
            return True
    return False


# Replace first occurrences of vault note titles and headings with wikilinks.
#
# Scans content for mentions of existing note titles and headings from the
# vault map. Wraps the first occurrence of each in [[wikilinks]], skipping
# protected regions (frontmatter, code, existing links, headings).
#
# Args:
#     content: Markdown content to wikify.
#     vault_map: Current vault map with note summaries.
#     self_path: Path of the note being generated (excluded from linking).
#
# Returns:
#     Content with first occurrences of note titles/headings wrapped in wikilinks.
def wikify(content: str, vault_map: VaultMap, self_path: str | None = None) -> str:
    # Build targets: (match_text, link_text), titles first then headings
    seen: set[str] = set()
    targets: list[tuple[str, str]] = []

    for note in vault_map.notes:
        if note.path == self_path:
            continue

        # Titles
        if len(note.title) >= 3 and note.title.lower() not in seen:
            seen.add(note.title.lower())
            targets.append((note.title, f"[[{note.title}]]"))

    for note in vault_map.notes:
        if note.path == self_path:
            continue

        # Headings
        for heading in note.headings:
            if len(heading) >= 3 and heading.lower() not in seen:
                seen.add(heading.lower())
                targets.append((heading, f"[[{note.title}#{heading}]]"))

    if not targets:
        return content

    # Sort longest-first for greedy matching
    targets.sort(key=lambda t: len(t[0]), reverse=True)

    # Build lookup and combined regex
    lookup: dict[str, str] = {text.lower(): link for text, link in targets}
    alternation = "|".join(re.escape(text) for text, _ in targets)
    combined = re.compile(rf"\b({alternation})\b", re.IGNORECASE)

    protected_spans = _find_protected_spans(content)

    # Single pass: collect replacements
    claimed: set[str] = set()
    replacements: list[tuple[int, int, str]] = []

    for m in combined.finditer(content):
        key = m.group().lower()
        if key in claimed:
            continue
        if _overlaps(m.start(), m.end(), protected_spans):
            continue
        claimed.add(key)
        replacements.append((m.start(), m.end(), lookup[key]))

    # Splice replacements (already in document order)
    if not replacements:
        return content

    parts: list[str] = []
    prev = 0
    for start, end, link in replacements:
        parts.append(content[prev:start])
        parts.append(link)
        prev = end
    parts.append(content[prev:])

    return "".join(parts)
