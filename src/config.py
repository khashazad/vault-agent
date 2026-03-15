import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


# Application configuration loaded from environment variables.
@dataclass
class AppConfig:
    anthropic_api_key: str
    vault_path: str
    port: int
    zotero_api_key: str | None = None
    zotero_library_id: str | None = None
    zotero_library_type: str = "user"


# Load and validate application config from environment variables.
#
# Returns:
#     Populated AppConfig instance.
#
# Raises:
#     RuntimeError: If required env vars are missing or VAULT_PATH is invalid.
def load_config() -> AppConfig:
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is required")

    vault_path = os.environ.get("VAULT_PATH")
    if not vault_path:
        raise RuntimeError("VAULT_PATH environment variable is required")

    p = Path(vault_path)
    if not p.exists() or not p.is_dir():
        raise RuntimeError(
            f'VAULT_PATH "{vault_path}" does not exist or is not a directory'
        )

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
