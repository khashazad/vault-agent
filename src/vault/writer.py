import re

import frontmatter

from src.models import CreateNoteInput, UpdateNoteInput
from src.vault import validate_path


def compute_create(vault_path: str, inp: CreateNoteInput) -> str:
    """Validate and return proposed content without writing to disk."""
    full_path = validate_path(vault_path, inp.path)

    if full_path.exists():
        raise FileExistsError(
            f"Note already exists at {inp.path}. Use update_note to modify existing notes."
        )

    return inp.content


def compute_update(raw: str, inp: UpdateNoteInput) -> str:
    """Compute the result of an update operation on raw file content.
    Returns the updated content string without writing to disk.
    """
    if inp.operation == "append_section":
        content_to_append = inp.content or ""

        if inp.heading:
            heading_pattern = re.compile(
                rf"^(#{{1,6}})\s+{re.escape(inp.heading)}\s*$",
                re.MULTILINE,
            )
            match = heading_pattern.search(raw)

            if match:
                heading_level = len(match.group(1))
                insert_pos = match.end()
                rest = raw[insert_pos:]

                next_heading_pattern = re.compile(
                    rf"^#{{1,{heading_level}}}\s+",
                    re.MULTILINE,
                )
                next_match = next_heading_pattern.search(rest)

                if next_match:
                    section_end = insert_pos + next_match.start()
                    updated = (
                        raw[:section_end].rstrip()
                        + "\n\n"
                        + content_to_append
                        + "\n\n"
                        + raw[section_end:]
                    )
                else:
                    updated = raw.rstrip() + "\n\n" + content_to_append + "\n"
            else:
                updated = (
                    raw.rstrip()
                    + "\n\n## "
                    + inp.heading
                    + "\n\n"
                    + content_to_append
                    + "\n"
                )
        else:
            updated = raw.rstrip() + "\n\n" + content_to_append + "\n"

        return updated

    if inp.operation == "add_tags":
        new_tags = inp.tags or []
        if not new_tags:
            return raw

        try:
            post = frontmatter.loads(raw)
        except Exception as e:
            raise ValueError(
                f"Failed to parse frontmatter in {inp.path}. Cannot add tags."
            ) from e

        existing_tags: list[str] = (
            list(post.metadata.get("tags", []))
            if isinstance(post.metadata.get("tags"), list)
            else []
        )
        merged = list(dict.fromkeys(existing_tags + new_tags))
        post.metadata["tags"] = merged

        return frontmatter.dumps(post)

    raise ValueError(f"Unknown operation: {inp.operation}")


def create_note(vault_path: str, inp: CreateNoteInput) -> str:
    full_path = validate_path(vault_path, inp.path)

    if full_path.exists():
        raise FileExistsError(
            f"Note already exists at {inp.path}. Use update_note to modify existing notes."
        )

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(inp.content, encoding="utf-8")

    return f"Created note at {inp.path}"


def update_note(vault_path: str, inp: UpdateNoteInput) -> str:
    full_path = validate_path(vault_path, inp.path)

    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {inp.path}")

    raw = full_path.read_text(encoding="utf-8")
    updated = compute_update(raw, inp)

    full_path.write_text(updated, encoding="utf-8")

    if inp.operation == "append_section":
        heading_msg = f' under "{inp.heading}"' if inp.heading else ""
        return f"Appended content to {inp.path}{heading_msg}"

    if inp.operation == "add_tags":
        return f"Added tags to {inp.path}"

    return f"Updated {inp.path}"
