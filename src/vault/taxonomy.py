import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath

import frontmatter as fm_lib

from src.agent.diff import generate_diff
from src.models import Changeset, ContentItem, ProposedChange
from src.models.migration import TagNode
from src.models.vault import LinkTargetInfo, TagInfo, VaultTaxonomy
from src.vault import iter_markdown_files
from src.vault.reader import extract_wikilinks, parse_frontmatter

INLINE_TAG_RE = re.compile(r"(?<!\w)#([a-zA-Z][\w/-]*)")
HEADING_LINE_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".ico",
})


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
        if not any(t.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
    ]

    return VaultTaxonomy(
        folders=sorted(folders),
        tags=tags,
        tag_hierarchy=hierarchy,
        link_targets=links,
        total_notes=total_notes,
    )


WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]")


# Apply a list of curation operations to vault notes, returning a Changeset.
#
# Each operation finds affected notes, generates modified content, and
# produces a ProposedChange with a unified diff. All changes are bundled
# into a single Changeset persisted to SQLite.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     operations: List of TaxonomyCurationOp to apply.
#
# Returns:
#     Changeset with proposed changes for review.
def apply_taxonomy_curation(
    vault_path: str,
    operations: list,
) -> Changeset:
    changes: list[ProposedChange] = []

    for op in operations:
        if op.op in ("rename_tag", "merge_tags", "delete_tag"):
            changes.extend(_apply_tag_op(vault_path, op))
        elif op.op in ("rename_link", "merge_links", "delete_link"):
            changes.extend(_apply_link_op(vault_path, op))
        elif op.op in ("rename_folder", "move_folder", "delete_folder"):
            changes.extend(_apply_folder_op(vault_path, op))

    changeset = Changeset(
        id=str(uuid.uuid4()),
        items=[ContentItem(
            text=f"Taxonomy curation: {len(operations)} operation(s)",
            source="vault-taxonomy",
            source_type="web",
        )],
        changes=changes,
        reasoning=_build_reasoning(operations),
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
        source_type="web",
    )
    return changeset


def _build_reasoning(operations: list) -> str:
    parts = []
    for op in operations:
        if op.value:
            parts.append(f"{op.op}: {op.target} -> {op.value}")
        else:
            parts.append(f"{op.op}: {op.target}")
    return "Taxonomy curation: " + "; ".join(parts)


def _apply_tag_op(vault_path: str, op) -> list[ProposedChange]:
    changes = []
    for md_file, file_path in iter_markdown_files(vault_path):
        raw = md_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(raw)
        note_tags = extract_tags(fm, body)

        if op.target not in note_tags:
            continue

        new_raw = raw
        if op.op == "rename_tag":
            new_raw = _replace_tag_in_note(raw, fm, op.target, op.value)
        elif op.op == "merge_tags":
            new_raw = _replace_tag_in_note(raw, fm, op.target, op.value)
        elif op.op == "delete_tag":
            new_raw = _remove_tag_from_note(raw, fm, op.target)

        if new_raw != raw:
            diff = generate_diff(file_path, raw, new_raw)
            changes.append(ProposedChange(
                id=str(uuid.uuid4()),
                tool_name="update_note",
                input={"path": file_path, "content": new_raw},
                original_content=raw,
                proposed_content=new_raw,
                diff=diff,
            ))
    return changes


def _replace_tag_in_note(raw: str, fm: dict, old_tag: str, new_tag: str) -> str:
    # Use python-frontmatter for safe YAML rewriting
    post = fm_lib.loads(raw)
    fm_tags = post.metadata.get("tags", [])
    if isinstance(fm_tags, list) and old_tag in fm_tags:
        post.metadata["tags"] = [new_tag if t == old_tag else t for t in fm_tags]
    elif isinstance(fm_tags, str) and fm_tags == old_tag:
        post.metadata["tags"] = [new_tag]

    # Replace inline #tag occurrences in body
    new_content = re.sub(
        rf"(?<!\w)#{re.escape(old_tag)}(?!\w)",
        f"#{new_tag}",
        post.content,
    )
    post.content = new_content
    return fm_lib.dumps(post)


def _remove_tag_from_note(raw: str, fm: dict, tag: str) -> str:
    post = fm_lib.loads(raw)
    fm_tags = post.metadata.get("tags", [])
    if isinstance(fm_tags, list) and tag in fm_tags:
        post.metadata["tags"] = [t for t in fm_tags if t != tag]
    elif isinstance(fm_tags, str) and fm_tags == tag:
        post.metadata["tags"] = []

    # Remove inline #tag occurrences
    new_content = re.sub(rf"(?<!\w)#{re.escape(tag)}(?!\w)\s?", "", post.content)
    post.content = new_content
    return fm_lib.dumps(post)


def _apply_link_op(vault_path: str, op) -> list[ProposedChange]:
    changes = []
    for md_file, file_path in iter_markdown_files(vault_path):
        raw = md_file.read_text(encoding="utf-8")
        if f"[[{op.target}" not in raw:
            continue

        new_raw = raw
        if op.op == "rename_link":
            new_raw = re.sub(
                rf"\[\[{re.escape(op.target)}(\|[^\]]+)?\]\]",
                lambda m: f"[[{op.value}{m.group(1) or ''}]]",
                raw,
            )
        elif op.op == "merge_links":
            new_raw = re.sub(
                rf"\[\[{re.escape(op.target)}(\|[^\]]+)?\]\]",
                lambda m: f"[[{op.value}{m.group(1) or ''}]]",
                raw,
            )
        elif op.op == "delete_link":
            new_raw = re.sub(
                rf"\[\[{re.escape(op.target)}(\|([^\]]+))?\]\]",
                lambda m: m.group(2) or op.target,
                raw,
            )

        if new_raw != raw:
            diff = generate_diff(file_path, raw, new_raw)
            changes.append(ProposedChange(
                id=str(uuid.uuid4()),
                tool_name="update_note",
                input={"path": file_path, "content": new_raw},
                original_content=raw,
                proposed_content=new_raw,
                diff=diff,
            ))
    return changes


def _apply_folder_op(vault_path: str, op) -> list[ProposedChange]:
    changes = []
    for md_file, file_path in iter_markdown_files(vault_path):
        folder = str(PurePosixPath(file_path).parent)
        if folder != op.target:
            continue

        filename = PurePosixPath(file_path).name
        if op.op in ("rename_folder", "move_folder"):
            new_path = f"{op.value}/{filename}"
        elif op.op == "delete_folder":
            new_path = filename
        else:
            continue

        raw = md_file.read_text(encoding="utf-8")
        diff = generate_diff(file_path, raw, raw)
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="update_note",
            input={"path": new_path, "original_path": file_path, "content": raw},
            original_content=raw,
            proposed_content=raw,
            diff=f"Move: {file_path} -> {new_path}",
        ))
    return changes
