from pathlib import Path


# Resolve a note path against the vault root and verify it stays within bounds.
#
# Args:
#     vault_path: Absolute path to the vault root directory.
#     note_path: Relative path to a note within the vault.
#
# Returns:
#     Resolved absolute Path to the note.
#
# Raises:
#     ValueError: If the resolved path escapes the vault directory.
def validate_path(vault_path: str, note_path: str) -> Path:
    resolved = Path(vault_path, note_path).resolve()
    vault_resolved = Path(vault_path).resolve()
    if not resolved.is_relative_to(vault_resolved):
        raise ValueError(f'Path "{note_path}" escapes the vault directory')
    return resolved
