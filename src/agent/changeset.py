from src.models import Changeset, CreateNoteInput, UpdateNoteInput
from src.vault.writer import create_note, update_note


def apply_changeset(
    vault_path: str,
    changeset: Changeset,
    approved_ids: list[str] | None = None,
) -> dict:
    """Apply approved changes from a changeset to disk.
    If approved_ids is None, apply all changes with status 'approved'.
    """
    applied: list[str] = []
    failed: list[dict] = []

    for change in changeset.changes:
        # Skip if not approved
        if approved_ids is not None:
            if change.id not in approved_ids:
                continue
        elif change.status != "approved":
            continue

        try:
            if change.tool_name == "create_note":
                inp = CreateNoteInput(**change.input)
                create_note(vault_path, inp)
                applied.append(change.id)

            elif change.tool_name == "update_note":
                inp = UpdateNoteInput(**change.input)
                update_note(vault_path, inp)
                applied.append(change.id)

            change.status = "applied"

        except Exception as err:
            failed.append({"id": change.id, "error": str(err)})

    return {"applied": applied, "failed": failed}
