import pytest
from pathlib import Path

from src.agent.changeset import apply_changeset
from tests.factories import make_changeset, make_replace_change, make_delete_change, make_proposed_change


class TestApplyReplaceNote:
    def test_replace_overwrites_file(self, tmp_vault):
        vault = str(tmp_vault)
        change = make_replace_change(
            input={"path": "Projects/My Project.md", "content": "# New\n\nReplaced."},
            proposed_content="# New\n\nReplaced.",
            status="approved",
        )
        cs = make_changeset(changes=[change], source_type="clawdy", items=[], routing=None)
        result = apply_changeset(vault, cs)
        assert change.id in result["applied"]
        assert (tmp_vault / "Projects/My Project.md").read_text() == "# New\n\nReplaced."

    def test_replace_missing_file_fails(self, tmp_vault):
        vault = str(tmp_vault)
        change = make_replace_change(
            input={"path": "Nonexistent.md", "content": "x"},
            status="approved",
        )
        cs = make_changeset(changes=[change], source_type="clawdy", items=[], routing=None)
        result = apply_changeset(vault, cs)
        assert len(result["failed"]) == 1


class TestApplyDeleteNote:
    def test_delete_removes_file(self, tmp_vault):
        vault = str(tmp_vault)
        change = make_delete_change(
            input={"path": "daily/2024-01-01.md"},
            status="approved",
        )
        cs = make_changeset(changes=[change], source_type="clawdy", items=[], routing=None)
        result = apply_changeset(vault, cs)
        assert change.id in result["applied"]
        assert not (tmp_vault / "daily/2024-01-01.md").exists()

    def test_delete_missing_file_fails(self, tmp_vault):
        vault = str(tmp_vault)
        change = make_delete_change(
            input={"path": "Nonexistent.md"},
            status="approved",
        )
        cs = make_changeset(changes=[change], source_type="clawdy", items=[], routing=None)
        result = apply_changeset(vault, cs)
        assert len(result["failed"]) == 1
