import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.agent.diff import generate_diff
from src.models import Changeset, ProposedChange
from src.vault import iter_markdown_files

logger = logging.getLogger("vault-agent")

# File change tuple: (relative_path, main_content, copy_content)
FileChange = tuple[str, str, str]
# Delete tuple: (relative_path, main_content)
FileDelete = tuple[str, str]
# Create tuple: (relative_path, copy_content)
FileCreate = tuple[str, str]


# Diff all .md files between main vault and copy vault.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#
# Returns:
#     Tuple of (modified, created, deleted) file lists.
def diff_vaults(
    main_vault: str, copy_vault: str
) -> tuple[list[FileChange], list[FileCreate], list[FileDelete]]:
    main_files: dict[str, str] = {}
    for _, rel in iter_markdown_files(main_vault):
        content = Path(main_vault, rel).read_text(encoding="utf-8")
        main_files[rel] = content

    copy_files: dict[str, str] = {}
    for _, rel in iter_markdown_files(copy_vault):
        content = Path(copy_vault, rel).read_text(encoding="utf-8")
        copy_files[rel] = content

    modified: list[FileChange] = []
    created: list[FileCreate] = []
    deleted: list[FileDelete] = []

    # Files in copy but not main = created
    # Files in both but different = modified
    for rel, copy_content in copy_files.items():
        if rel not in main_files:
            created.append((rel, copy_content))
        elif copy_content != main_files[rel]:
            modified.append((rel, main_files[rel], copy_content))

    # Files in main but not copy = deleted
    for rel, main_content in main_files.items():
        if rel not in copy_files:
            deleted.append((rel, main_content))

    return modified, created, deleted


# Build a Changeset from vault differences.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#
# Returns:
#     Changeset with one ProposedChange per changed file, or None if no changes.
def create_clawdy_changeset(
    main_vault: str, copy_vault: str
) -> Changeset | None:
    modified, created, deleted = diff_vaults(main_vault, copy_vault)

    if not modified and not created and not deleted:
        return None

    changes: list[ProposedChange] = []

    for rel, original, proposed in modified:
        diff = generate_diff(rel, original, proposed)
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="replace_note",
            input={"path": rel, "content": proposed},
            original_content=original,
            proposed_content=proposed,
            diff=diff,
        ))

    for rel, content in created:
        diff = generate_diff(rel, "", content)
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="create_note",
            input={"path": rel, "content": content},
            original_content=None,
            proposed_content=content,
            diff=diff,
        ))

    for rel, original in deleted:
        diff = generate_diff(rel, original, "")
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="delete_note",
            input={"path": rel},
            original_content=original,
            proposed_content="",
            diff=diff,
        ))

    return Changeset(
        id=str(uuid.uuid4()),
        changes=changes,
        reasoning="Changes detected from OpenClaw sync",
        source_type="clawdy",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
