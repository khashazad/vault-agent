import re

INLINE_TAG_RE = re.compile(r"(?<!\w)#([a-zA-Z][\w/-]*)")
HEADING_LINE_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)


# Extract all tags from a note's frontmatter and body content.
#
# Frontmatter tags come from metadata["tags"] (list or string).
# Inline tags are #tag patterns in body, excluding headings and code blocks.
#
# Args:
#     frontmatter: Parsed YAML metadata dict.
#     body: Markdown body content (without frontmatter).
#
# Returns:
#     Set of tag names (without # prefix).
def extract_tags(frontmatter: dict, body: str) -> set[str]:
    tags: set[str] = set()

    # Frontmatter tags
    fm_tags = frontmatter.get("tags", [])
    if isinstance(fm_tags, str):
        tags.add(fm_tags)
    elif isinstance(fm_tags, list):
        for t in fm_tags:
            if isinstance(t, str):
                tags.add(t)

    # Strip fenced code blocks before scanning for inline tags
    cleaned = FENCED_CODE_RE.sub("", body)

    # Process line by line, skipping heading lines
    for line in cleaned.splitlines():
        if HEADING_LINE_RE.match(line):
            continue
        for m in INLINE_TAG_RE.finditer(line):
            tags.add(m.group(1))

    return tags
