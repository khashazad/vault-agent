import re
from collections import Counter
from pathlib import PurePosixPath

from src.models.migration import TagNode
from src.models.vault import LinkTargetInfo, TagInfo, VaultTaxonomy
from src.vault import iter_markdown_files
from src.vault.reader import extract_wikilinks, parse_frontmatter

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


# Group flat tag-count pairs into a hierarchical TagNode tree.
#
# Tags with slashes (e.g. "research/ai") become children of their prefix.
# Parent nodes are created implicitly if they don't exist as standalone tags.
#
# Args:
#     tag_counts: Dict mapping tag name to usage count.
#
# Returns:
#     Sorted list of root TagNode objects.
def build_tag_hierarchy(tag_counts: dict[str, int]) -> list[TagNode]:
    # Build a nested dict structure
    roots: dict[str, dict] = {}

    for tag in sorted(tag_counts.keys()):
        parts = tag.split("/")
        node = roots
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    def _build_nodes(tree: dict[str, dict]) -> list[TagNode]:
        nodes = []
        for name in sorted(tree.keys()):
            children = _build_nodes(tree[name])
            nodes.append(TagNode(name=name, children=children))
        return nodes

    return _build_nodes(roots)


# Scan the vault and build a complete taxonomy of folders, tags, and link targets.
#
# Single pass over all markdown files. Extracts frontmatter tags, inline tags,
# folder paths, and wikilink targets with usage counts.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#
# Returns:
#     VaultTaxonomy with folders, flat tags, tag hierarchy, and link targets.
def build_vault_taxonomy(vault_path: str) -> VaultTaxonomy:
    tag_counter: Counter[str] = Counter()
    link_counter: Counter[str] = Counter()
    folders: set[str] = set()
    total_notes = 0

    for md_file, file_path in iter_markdown_files(vault_path):
        total_notes += 1
        raw = md_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)

        # Folders
        folder = str(PurePosixPath(file_path).parent)
        if folder != ".":
            folders.add(folder)

        # Tags
        note_tags = extract_tags(fm, body)
        tag_counter.update(note_tags)

        # Wikilinks
        wikilinks = extract_wikilinks(body)
        link_counter.update(wikilinks)

    tag_counts = dict(tag_counter)
    tags = [TagInfo(name=n, count=c) for n, c in sorted(tag_counts.items())]
    hierarchy = build_tag_hierarchy(tag_counts)
    links = [
        LinkTargetInfo(title=t, count=c)
        for t, c in sorted(link_counter.items(), key=lambda x: -x[1])
    ]

    return VaultTaxonomy(
        folders=sorted(folders),
        tags=tags,
        tag_hierarchy=hierarchy,
        link_targets=links,
        total_notes=total_notes,
    )
