import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    anthropic_api_key: str
    vault_path: str
    port: int
    voyage_api_key: str
    lancedb_path: str = ".lancedb"


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

    port = int(os.environ.get("PORT", "3000"))

    voyage_api_key = os.environ.get("VOYAGE_API_KEY")
    if not voyage_api_key:
        raise RuntimeError("VOYAGE_API_KEY environment variable is required")

    lancedb_path = os.environ.get("LANCEDB_PATH", ".lancedb")

    return AppConfig(
        anthropic_api_key=anthropic_api_key,
        vault_path=vault_path,
        port=port,
        voyage_api_key=voyage_api_key,
        lancedb_path=lancedb_path,
    )
