from pathlib import Path


def validate_path(vault_path: str, note_path: str) -> Path:
    resolved = Path(vault_path, note_path).resolve()
    vault_resolved = Path(vault_path).resolve()
    if not resolved.is_relative_to(vault_resolved):
        raise ValueError(f'Path "{note_path}" escapes the vault directory')
    return resolved
