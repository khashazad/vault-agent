from pathlib import Path

from src.store import get_migration_store


def write_migrated_note(target_vault: str, target_path: str, content: str) -> None:
    full = Path(target_vault) / target_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")


def apply_migration(target_vault: str, job_id: str) -> dict:
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
