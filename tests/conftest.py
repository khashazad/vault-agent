import os
from pathlib import Path

import pytest

from src.config import AppConfig


@pytest.fixture
def tmp_vault(tmp_path: Path) -> Path:
    """Temp vault directory with .obsidian/ marker and sample notes."""
    (tmp_path / ".obsidian").mkdir()

    # Sample notes for testing
    notes = {
        "Projects/My Project.md": (
            "---\ntags: [project]\ncreated: 2024-01-01\n---\n\n"
            "# My Project\n\nA sample project note.\n\n"
            "## Overview\n\nThis project covers [[Machine Learning]] topics.\n\n"
            "## References\n\nSee [[Papers/Some Paper]].\n"
        ),
        "Topics/Machine Learning.md": (
            "---\ntags: [topic, ml]\n---\n\n"
            "# Machine Learning\n\n"
            "A broad topic note.\n\n"
            "## Key Concepts\n\n"
            "- Supervised learning\n- Unsupervised learning\n\n"
            "## Related\n\n[[Projects/My Project]]\n"
        ),
        "Papers/Some Paper.md": (
            "---\ntags: [source/paper]\ncreated: 2024-06-15\n"
            "aliases:\n  - \"Paper - ABC123\"\n---\n\n"
            "# Some Paper Title\n\n"
            "> [!ad-abstract]\n> A paper about things.\n\n"
            "## Key Findings\n\n- ! Important finding\n"
        ),
        "daily/2024-01-01.md": (
            "---\ntags: [daily]\n---\n\n"
            "# 2024-01-01\n\nDaily note content.\n"
        ),
    }

    for rel_path, content in notes.items():
        p = tmp_path / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    return tmp_path


@pytest.fixture
def app_config(tmp_vault: Path, tmp_path: Path) -> AppConfig:
    """AppConfig pointing at tmp_vault with fake API keys."""
    return AppConfig(
        anthropic_api_key="sk-ant-test-fake-key",
        vault_path=str(tmp_vault),
        port=3000,
        voyage_api_key="pa-test-fake-key",
        lancedb_path=str(tmp_path / ".lancedb"),
        zotero_api_key="zotero-test-key",
        zotero_library_id="12345",
        zotero_library_type="user",
    )
