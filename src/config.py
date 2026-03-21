import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


# Application configuration loaded from environment variables and DB settings.
@dataclass
class AppConfig:
    anthropic_api_key: str
    vault_path: str | None
    port: int
    zotero_api_key: str | None = None
    zotero_library_id: str | None = None
    zotero_library_type: str = "user"


# Load and validate application config from env vars + persisted settings.
#
# Returns:
#     Populated AppConfig instance. vault_path may be None if not yet selected.
#
# Raises:
#     RuntimeError: If ANTHROPIC_API_KEY is missing.
def load_config() -> AppConfig:
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is required")

    # Load vault_path from DB only — env var no longer used
    vault_path = _load_vault_path_from_db()

    port = int(os.environ.get("PORT", "3456"))

    zotero_api_key = os.environ.get("ZOTERO_API_KEY")
    zotero_library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    zotero_library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")

    return AppConfig(
        anthropic_api_key=anthropic_api_key,
        vault_path=vault_path,
        port=port,
        zotero_api_key=zotero_api_key,
        zotero_library_id=zotero_library_id,
        zotero_library_type=zotero_library_type,
    )


# Read vault_path from SettingsStore and validate it still exists.
def _load_vault_path_from_db() -> str | None:
    from src.db import get_settings_store

    stored = get_settings_store().get("vault_path")
    if stored and Path(stored).is_dir():
        return stored
    return None
