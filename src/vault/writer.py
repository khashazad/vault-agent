import re

from src.models import CreateNoteInput, UpdateNoteInput
from src.vault import validate_path


# Compute the result of an append operation on raw file content without writing to disk.
#
# Inserts content under the specified heading if found, creates the heading if missing,
# or appends to end of file if no heading specified.
#
# Args:
#     raw: Current raw file content.
#     inp: UpdateNoteInput with heading and content to append.
#
# Returns:
#     The full updated content string.
def compute_update(raw: str, inp: UpdateNoteInput) -> str:
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


# Create a new note on disk, failing atomically if the file already exists.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     inp: CreateNoteInput with target path and content.
#
# Returns:
#     Confirmation message with the created path.
def create_note(vault_path: str, inp: CreateNoteInput) -> str:
    full_path = validate_path(vault_path, inp.path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation ('x' mode) atomically prevents TOCTOU race
    with open(full_path, "x", encoding="utf-8") as f:
        f.write(inp.content)

    return f"Created note at {inp.path}"


# Append content to an existing note, optionally under a specific heading.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     inp: UpdateNoteInput with target path, heading, and content.
#
# Returns:
#     Confirmation message describing the append.
#
# Raises:
#     FileNotFoundError: When the target note does not exist.
def update_note(vault_path: str, inp: UpdateNoteInput) -> str:
    full_path = validate_path(vault_path, inp.path)

    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {inp.path}")

    raw = full_path.read_text(encoding="utf-8")
    updated = compute_update(raw, inp)

    full_path.write_text(updated, encoding="utf-8")

    heading_msg = f' under "{inp.heading}"' if inp.heading else ""
    return f"Appended content to {inp.path}{heading_msg}"


# Overwrite an existing note with new content.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     note_path: Relative path to the note within the vault.
#     content: New file content.
#
# Returns:
#     Confirmation message.
#
# Raises:
#     FileNotFoundError: When the target note does not exist.
#     ValueError: When the path escapes the vault directory.
def replace_note(vault_path: str, note_path: str, content: str) -> str:
    full_path = validate_path(vault_path, note_path)
    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")
    full_path.write_text(content, encoding="utf-8")
    return f"Replaced note at {note_path}"


# Delete an existing note from the vault.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     note_path: Relative path to the note within the vault.
#
# Returns:
#     Confirmation message.
#
# Raises:
#     FileNotFoundError: When the target note does not exist.
#     ValueError: When the path escapes the vault directory.
def delete_note(vault_path: str, note_path: str) -> str:
    full_path = validate_path(vault_path, note_path)
    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")
    full_path.unlink()
    return f"Deleted note at {note_path}"
