import shutil
from pathlib import Path

from src.db import get_migration_store


# Copy .obsidian/ settings and Files/ attachments from source to target vault.
#
# Args:
#     source_vault: Absolute path to the source Obsidian vault.
#     target_vault: Absolute path to the target vault.
def copy_vault_assets(source_vault: str, target_vault: str) -> None:
    src = Path(source_vault)
    dst = Path(target_vault)
    dst.mkdir(parents=True, exist_ok=True)

    for dirname in (".obsidian", "Files"):
        src_dir = src / dirname
        dst_dir = dst / dirname
        if src_dir.is_dir():
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir, symlinks=False)


# Write a single migrated note to the target vault, creating parent dirs.
#
# Args:
#     target_vault: Absolute path to the target vault root.
#     target_path: Relative path for the note within the target vault.
#     content: Migrated markdown content to write.
def write_migrated_note(target_vault: str, target_path: str, content: str) -> None:
    full = Path(target_vault) / target_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


# Write all approved notes for a migration job to the target vault.
#
# Copies .obsidian/ and Files/ from source vault first, then iterates
# approved notes, writes each to disk, and updates status to 'applied'
# or 'failed' in the store.
#
# Args:
#     source_vault: Absolute path to the source Obsidian vault.
#     target_vault: Absolute path to the target vault root.
#     job_id: Migration job identifier.
#
# Returns:
#     Dict with 'applied' (list of note IDs) and 'failed' (list of error dicts).
def apply_migration(source_vault: str, target_vault: str, job_id: str) -> dict:
    copy_vault_assets(source_vault, target_vault)
    store = get_migration_store()
    applied: list[str] = []
    failed: list[dict[str, str]] = []

    notes, _ = store.get_notes_by_job(job_id, status="approved", limit=10000)
    for note in notes:
        if not note.proposed_content:
            failed.append({"id": note.id, "error": "No proposed content"})
            continue
        try:
            write_migrated_note(target_vault, note.target_path, note.proposed_content)
            note.status = "applied"
            store.update_note(job_id, note)
            applied.append(note.id)
        except Exception as e:
            note.status = "failed"
            note.error = str(e)
            store.update_note(job_id, note)
            failed.append({"id": note.id, "error": str(e)})

    return {"applied": applied, "failed": failed}
