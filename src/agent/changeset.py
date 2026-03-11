from src.models import Changeset, CreateNoteInput, UpdateNoteInput
from src.vault.writer import create_note, update_note


# Write approved changes from a changeset to the vault filesystem.
#
# Iterates changeset.changes and applies each via create_note or update_note.
# If approved_ids is provided, only those changes are applied; otherwise
# applies all changes with status 'approved'.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     changeset: Changeset containing ProposedChange objects to apply.
#     approved_ids: Explicit list of change IDs to apply. If None, uses status field.
#
# Returns:
#     Dict with 'applied' (list of change IDs) and 'failed' (list of {id, error}).
def apply_changeset(
    vault_path: str,
    changeset: Changeset,
    approved_ids: list[str] | None = None,
) -> dict:
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
