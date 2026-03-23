import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.agent.diff import generate_diff
from src.clawdy.git import pull
from src.db.changesets import ChangesetStore
from src.db.settings import SettingsStore
from src.models import Changeset, ProposedChange
from src.vault import iter_markdown_files

logger = logging.getLogger("vault-agent")

# File change tuple: (relative_path, main_content, copy_content)
FileChange = tuple[str, str, str]
# Delete tuple: (relative_path, main_content)
FileDelete = tuple[str, str]
# Create tuple: (relative_path, copy_content)
FileCreate = tuple[str, str]


# Hash all .md files in a vault directory.
#
# Args:
#     vault_path: Path to the vault.
#
# Returns:
#     Dict mapping relative path to MD5 hex digest.
def snapshot_vault(vault_path: str) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for full_path, rel in iter_markdown_files(vault_path):
        content = full_path.read_bytes()
        hashes[rel] = hashlib.md5(content).hexdigest()
    return hashes


# DiffSet groups the three diff lists into a single tuple.
DiffSet = tuple[list[FileChange], list[FileCreate], list[FileDelete]]


# Split vault diffs into OpenClaw-originated and main-vault-originated.
#
# Args:
#     modified: Modified file tuples from diff_vaults.
#     created: Created file tuples from diff_vaults.
#     deleted: Deleted file tuples from diff_vaults.
#     pull_changed: Set of relative paths that changed during git pull.
#
# Returns:
#     (openclaw_diffs, main_diffs) where each is (modified, created, deleted).
def partition_diff(
    modified: list[FileChange],
    created: list[FileCreate],
    deleted: list[FileDelete],
    pull_changed: set[str],
) -> tuple[DiffSet, DiffSet]:
    oc_mod = [m for m in modified if m[0] in pull_changed]
    oc_cre = [c for c in created if c[0] in pull_changed]
    oc_del = [d for d in deleted if d[0] in pull_changed]

    mn_mod = [m for m in modified if m[0] not in pull_changed]
    mn_cre = [c for c in created if c[0] not in pull_changed]
    mn_del = [d for d in deleted if d[0] not in pull_changed]

    return (oc_mod, oc_cre, oc_del), (mn_mod, mn_cre, mn_del)


# Sync user-originated changes from main vault to copy vault.
#
# For modified files, overwrites copy with main content.
# For created (in copy not main), deletes from copy (user deleted from main).
# For deleted (in main not copy), creates in copy from main.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#     modified: Modified file tuples (user-originated only).
#     created: Created file tuples (user-originated only).
#     deleted: Deleted file tuples (user-originated only).
#
# Returns:
#     Number of files synced.
def sync_main_to_copy(
    main_vault: str,
    copy_vault: str,
    modified: list[FileChange],
    created: list[FileCreate],
    deleted: list[FileDelete],
) -> int:
    count = 0

    for rel, _main_content, _copy_content in modified:
        main_file = Path(main_vault, rel)
        copy_file = Path(copy_vault, rel)
        copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")
        count += 1

    for rel, _copy_content in created:
        copy_file = Path(copy_vault, rel)
        if copy_file.exists():
            copy_file.unlink()
            count += 1

    for rel, _main_content in deleted:
        main_file = Path(main_vault, rel)
        copy_file = Path(copy_vault, rel)
        copy_file.parent.mkdir(parents=True, exist_ok=True)
        copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")
        count += 1

    return count


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
    for full_path, rel in iter_markdown_files(main_vault):
        main_files[rel] = full_path.read_text(encoding="utf-8")

    copy_files: dict[str, str] = {}
    for full_path, rel in iter_markdown_files(copy_vault):
        copy_files[rel] = full_path.read_text(encoding="utf-8")

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


# Sync the copy vault to match the main vault for rejected changes.
#
# For rejected changes, overwrites copy vault files with main vault content.
# For applied changes, no action needed (main vault already updated).
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#     changes_map: Dict of {relative_path: {"tool_name": str, "status": str}}.
def converge_vaults(
    main_vault: str,
    copy_vault: str,
    changes_map: dict[str, dict[str, str]],
) -> None:
    for rel_path, info in changes_map.items():
        if info["status"] != "rejected":
            continue

        main_file = Path(main_vault, rel_path)
        copy_file = Path(copy_vault, rel_path)

        if info["tool_name"] == "replace_note":
            # Rejected modification: restore main's version in copy
            copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")

        elif info["tool_name"] == "create_note":
            # Rejected creation: delete from copy
            if copy_file.exists():
                copy_file.unlink()

        elif info["tool_name"] == "delete_note":
            # Rejected deletion: restore file in copy from main
            copy_file.parent.mkdir(parents=True, exist_ok=True)
            copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")


# Background service that polls the copy vault and creates changesets.
class ClawdyService:
    # Initialize from SettingsStore config.
    #
    # Args:
    #     settings_store: SettingsStore for reading config.
    #     changeset_store: ChangesetStore for persisting changesets.
    def __init__(self, settings_store: SettingsStore, changeset_store: ChangesetStore):
        self._settings = settings_store
        self._changeset_store = changeset_store
        self._task: asyncio.Task | None = None
        self.last_poll: str | None = None
        self.last_error: str | None = None

        self.copy_vault_path = self._settings.get("clawdy_copy_vault_path")
        interval_str = self._settings.get("clawdy_interval")
        self.interval = int(interval_str) if interval_str else 300
        enabled_str = self._settings.get("clawdy_enabled")
        self.enabled = enabled_str == "true" if enabled_str else False

    # Run a single poll cycle: pull, diff, create changeset.
    #
    # Args:
    #     main_vault: Path to the main vault.
    def poll(self, main_vault: str) -> None:
        if not self.enabled or not self.copy_vault_path:
            return

        # Check for pending clawdy changeset
        pending, count = self._changeset_store.get_all_filtered(
            status="pending", source_type="clawdy", limit=1
        )
        if count > 0:
            logger.debug("clawdy: skipping poll, pending changeset exists")
            return

        try:
            pull(self.copy_vault_path)
        except Exception as e:
            self.last_error = str(e)
            logger.warning("clawdy: git pull failed: %s", e)
            return

        try:
            cs = create_clawdy_changeset(main_vault, self.copy_vault_path)
            if cs:
                self._changeset_store.set(cs)
                logger.info("clawdy: created changeset %s with %d changes", cs.id, len(cs.changes))
            self.last_error = None
            self.last_poll = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            self.last_error = str(e)
            logger.exception("clawdy: diff/changeset creation failed")

    # Start the background poll loop.
    #
    # Args:
    #     main_vault: Path to the main vault.
    async def start(self, main_vault: str) -> None:
        self._task = asyncio.create_task(self._poll_loop(main_vault))

    # Stop the background poll loop.
    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self, main_vault: str) -> None:
        while True:
            try:
                await asyncio.to_thread(self.poll, main_vault)
            except Exception:
                logger.exception("clawdy: unexpected error in poll loop")
            await asyncio.sleep(self.interval)
