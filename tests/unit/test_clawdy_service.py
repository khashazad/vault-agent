import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.clawdy.service import diff_vaults, create_clawdy_changeset, converge_vaults, ClawdyService, snapshot_vault


def _write(vault: Path, rel: str, content: str):
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


@pytest.fixture
def main_vault(tmp_path):
    vault = tmp_path / "main"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    _write(vault, "Notes/A.md", "# A\n\nOriginal content.")
    _write(vault, "Notes/B.md", "# B\n\nShared content.")
    _write(vault, "Notes/OnlyMain.md", "# OnlyMain\n\nContent.")
    return vault


@pytest.fixture
def copy_vault(tmp_path):
    vault = tmp_path / "copy"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    _write(vault, "Notes/A.md", "# A\n\nModified by OpenClaw.")
    _write(vault, "Notes/B.md", "# B\n\nShared content.")
    _write(vault, "Notes/OnlyCopy.md", "# OnlyCopy\n\nNew from agent.")
    return vault


class TestDiffVaults:
    def test_detects_modified_files(self, main_vault, copy_vault):
        modified, created, deleted = diff_vaults(str(main_vault), str(copy_vault))
        assert len(modified) == 1
        assert modified[0][0] == "Notes/A.md"

    def test_detects_created_files(self, main_vault, copy_vault):
        modified, created, deleted = diff_vaults(str(main_vault), str(copy_vault))
        assert len(created) == 1
        assert created[0][0] == "Notes/OnlyCopy.md"

    def test_detects_deleted_files(self, main_vault, copy_vault):
        modified, created, deleted = diff_vaults(str(main_vault), str(copy_vault))
        assert len(deleted) == 1
        assert deleted[0][0] == "Notes/OnlyMain.md"

    def test_identical_files_not_reported(self, main_vault, copy_vault):
        modified, created, deleted = diff_vaults(str(main_vault), str(copy_vault))
        paths = [m[0] for m in modified] + [c[0] for c in created] + [d[0] for d in deleted]
        assert "Notes/B.md" not in paths

    def test_no_changes_returns_empty(self, main_vault):
        modified, created, deleted = diff_vaults(str(main_vault), str(main_vault))
        assert modified == []
        assert created == []
        assert deleted == []


class TestCreateClawdyChangeset:
    def test_creates_changeset_with_all_change_types(self, main_vault, copy_vault):
        cs = create_clawdy_changeset(str(main_vault), str(copy_vault))
        assert cs is not None
        assert cs.source_type == "clawdy"
        assert len(cs.items) == 0
        assert cs.routing is None

        tool_names = {c.tool_name for c in cs.changes}
        assert tool_names == {"replace_note", "create_note", "delete_note"}

    def test_returns_none_when_no_changes(self, main_vault):
        cs = create_clawdy_changeset(str(main_vault), str(main_vault))
        assert cs is None

    def test_replace_change_has_correct_content(self, main_vault, copy_vault):
        cs = create_clawdy_changeset(str(main_vault), str(copy_vault))
        replace = [c for c in cs.changes if c.tool_name == "replace_note"][0]
        assert replace.original_content == "# A\n\nOriginal content."
        assert replace.proposed_content == "# A\n\nModified by OpenClaw."
        assert replace.diff  # non-empty diff

    def test_create_change_has_correct_content(self, main_vault, copy_vault):
        cs = create_clawdy_changeset(str(main_vault), str(copy_vault))
        create = [c for c in cs.changes if c.tool_name == "create_note"][0]
        assert create.original_content is None
        assert "OnlyCopy" in create.proposed_content

    def test_delete_change_has_empty_proposed(self, main_vault, copy_vault):
        cs = create_clawdy_changeset(str(main_vault), str(copy_vault))
        delete = [c for c in cs.changes if c.tool_name == "delete_note"][0]
        assert delete.proposed_content == ""
        assert delete.original_content == "# OnlyMain\n\nContent."


class TestConvergeVaults:
    def test_rejected_replace_copies_main_to_copy(self, main_vault, copy_vault):
        # A.md was modified in copy; rejecting should restore main's version
        changes_map = {
            "Notes/A.md": {"tool_name": "replace_note", "status": "rejected"}
        }
        converge_vaults(str(main_vault), str(copy_vault), changes_map)
        copy_content = (copy_vault / "Notes/A.md").read_text()
        main_content = (main_vault / "Notes/A.md").read_text()
        assert copy_content == main_content

    def test_rejected_create_deletes_from_copy(self, main_vault, copy_vault):
        changes_map = {
            "Notes/OnlyCopy.md": {"tool_name": "create_note", "status": "rejected"}
        }
        converge_vaults(str(main_vault), str(copy_vault), changes_map)
        assert not (copy_vault / "Notes/OnlyCopy.md").exists()

    def test_rejected_delete_restores_in_copy(self, main_vault, copy_vault):
        changes_map = {
            "Notes/OnlyMain.md": {"tool_name": "delete_note", "status": "rejected"}
        }
        converge_vaults(str(main_vault), str(copy_vault), changes_map)
        assert (copy_vault / "Notes/OnlyMain.md").exists()
        copy_content = (copy_vault / "Notes/OnlyMain.md").read_text()
        main_content = (main_vault / "Notes/OnlyMain.md").read_text()
        assert copy_content == main_content

    def test_applied_changes_no_op(self, main_vault, copy_vault):
        original_copy_content = (copy_vault / "Notes/A.md").read_text()
        changes_map = {
            "Notes/A.md": {"tool_name": "replace_note", "status": "applied"}
        }
        converge_vaults(str(main_vault), str(copy_vault), changes_map)
        # Applied changes are already in sync — copy unchanged
        assert (copy_vault / "Notes/A.md").read_text() == original_copy_content


class TestSnapshotVault:
    def test_hashes_md_files(self, main_vault):
        result = snapshot_vault(str(main_vault))
        assert "Notes/A.md" in result
        assert "Notes/B.md" in result
        assert "Notes/OnlyMain.md" in result
        assert len(result) == 3
        # Hashes are 32-char hex strings
        for v in result.values():
            assert len(v) == 32

    def test_ignores_non_md_files(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / ".obsidian").mkdir()
        _write(vault, "note.md", "content")
        (vault / "image.png").write_bytes(b"\x89PNG")
        result = snapshot_vault(str(vault))
        assert "note.md" in result
        assert "image.png" not in result

    def test_empty_vault(self, tmp_path):
        vault = tmp_path / "empty"
        vault.mkdir()
        (vault / ".obsidian").mkdir()
        result = snapshot_vault(str(vault))
        assert result == {}


class TestClawdyServiceInit:
    def test_init_with_defaults(self):
        settings = MagicMock()
        settings.get.return_value = None
        svc = ClawdyService(settings_store=settings, changeset_store=MagicMock())
        assert svc.enabled is False
        assert svc.copy_vault_path is None
        assert svc.interval == 300

    def test_init_loads_config(self):
        settings = MagicMock()
        settings.get.side_effect = lambda k: {
            "clawdy_copy_vault_path": "/some/path",
            "clawdy_interval": "60",
            "clawdy_enabled": "true",
        }.get(k)
        svc = ClawdyService(settings_store=settings, changeset_store=MagicMock())
        assert svc.copy_vault_path == "/some/path"
        assert svc.interval == 60
        assert svc.enabled is True


class TestClawdyServicePoll:
    def test_poll_skips_when_disabled(self):
        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = False
        svc.poll(main_vault="/main")
        cs_store.set.assert_not_called()

    def test_poll_skips_when_no_copy_vault(self):
        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = None
        svc.poll(main_vault="/main")
        cs_store.set.assert_not_called()

    @patch("src.clawdy.service.pull")
    @patch("src.clawdy.service.create_clawdy_changeset")
    def test_poll_creates_changeset_on_changes(self, mock_create, mock_pull):
        from tests.factories import make_changeset
        mock_cs = make_changeset(source_type="clawdy", items=[], routing=None)
        mock_create.return_value = mock_cs
        mock_pull.return_value = ""

        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = "/copy"
        svc.poll(main_vault="/main")

        cs_store.set.assert_called_once_with(mock_cs)

    @patch("src.clawdy.service.pull")
    @patch("src.clawdy.service.create_clawdy_changeset")
    def test_poll_skips_when_pending_changeset_exists(self, mock_create, mock_pull):
        from tests.factories import make_changeset
        mock_pull.return_value = ""

        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([make_changeset()], 1)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = "/copy"
        svc.poll(main_vault="/main")

        mock_create.assert_not_called()
