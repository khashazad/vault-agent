import asyncio
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.clawdy.service import diff_vaults, create_clawdy_changeset, converge_vaults, ClawdyService, snapshot_vault, partition_diff, sync_main_to_copy


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

    def test_uses_provided_diffs(self, main_vault, copy_vault):
        # Provide only modified diffs — should not call diff_vaults
        modified = [("Notes/A.md", "# A\n\nOriginal content.", "# A\n\nModified by OpenClaw.")]
        cs = create_clawdy_changeset(str(main_vault), str(copy_vault), diffs=(modified, [], []))
        assert cs is not None
        assert len(cs.changes) == 1
        assert cs.changes[0].tool_name == "replace_note"

    def test_provided_empty_diffs_returns_none(self, main_vault, copy_vault):
        cs = create_clawdy_changeset(str(main_vault), str(copy_vault), diffs=([], [], []))
        assert cs is None


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

    def test_applied_replace_copies_main_to_copy(self, main_vault, copy_vault):
        changes_map = {
            "Notes/A.md": {"tool_name": "replace_note", "status": "applied"}
        }
        converge_vaults(str(main_vault), str(copy_vault), changes_map)
        assert (copy_vault / "Notes/A.md").read_text() == (
            main_vault / "Notes/A.md"
        ).read_text()

    def test_applied_delete_removes_from_copy(self, main_vault, copy_vault):
        _write(copy_vault, "Notes/DeleteMe.md", "# Delete me")
        changes_map = {
            "Notes/DeleteMe.md": {"tool_name": "delete_note", "status": "applied"}
        }
        converge_vaults(str(main_vault), str(copy_vault), changes_map)
        assert not (copy_vault / "Notes/DeleteMe.md").exists()


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


class TestPartitionDiff:
    def test_separates_by_pull_changed(self):
        modified = [("Notes/A.md", "old", "new"), ("Notes/B.md", "old", "new")]
        created = [("Notes/C.md", "content")]
        deleted = [("Notes/D.md", "content")]
        pull_changed = {"Notes/A.md", "Notes/C.md"}

        openclaw, main = partition_diff(modified, created, deleted, pull_changed)

        assert openclaw[0] == [("Notes/A.md", "old", "new")]  # modified
        assert openclaw[1] == [("Notes/C.md", "content")]      # created
        assert openclaw[2] == []                                 # deleted

        assert main[0] == [("Notes/B.md", "old", "new")]       # modified
        assert main[1] == []                                     # created
        assert main[2] == [("Notes/D.md", "content")]           # deleted

    def test_empty_pull_changed_all_to_main(self):
        modified = [("A.md", "old", "new")]
        created = [("B.md", "content")]
        deleted = [("C.md", "content")]

        openclaw, main = partition_diff(modified, created, deleted, set())

        assert openclaw == ([], [], [])
        assert main == (modified, created, deleted)

    def test_all_in_pull_changed_all_to_openclaw(self):
        modified = [("A.md", "old", "new")]
        created = [("B.md", "content")]
        deleted = [("C.md", "content")]
        pull_changed = {"A.md", "B.md", "C.md"}

        openclaw, main = partition_diff(modified, created, deleted, pull_changed)

        assert openclaw == (modified, created, deleted)
        assert main == ([], [], [])

    def test_empty_diffs(self):
        openclaw, main = partition_diff([], [], [], {"A.md"})
        assert openclaw == ([], [], [])
        assert main == ([], [], [])


class TestSyncMainToCopy:
    def test_modified_overwrites_copy(self, main_vault, copy_vault):
        # A.md differs between vaults; sync should overwrite copy with main
        modified = [("Notes/A.md", main_vault.joinpath("Notes/A.md").read_text(), "ignored")]
        count = sync_main_to_copy(str(main_vault), str(copy_vault), modified, [], [])
        assert count == 1
        assert copy_vault.joinpath("Notes/A.md").read_text() == main_vault.joinpath("Notes/A.md").read_text()

    def test_created_in_copy_deleted_from_main(self, main_vault, copy_vault):
        # OnlyCopy.md exists in copy but not main → user deleted from main → delete from copy
        created = [("Notes/OnlyCopy.md", "content")]
        count = sync_main_to_copy(str(main_vault), str(copy_vault), [], created, [])
        assert count == 1
        assert not copy_vault.joinpath("Notes/OnlyCopy.md").exists()

    def test_deleted_from_copy_created_in_main(self, main_vault, copy_vault):
        # OnlyMain.md exists in main but not copy → user created in main → create in copy
        deleted = [("Notes/OnlyMain.md", main_vault.joinpath("Notes/OnlyMain.md").read_text())]
        count = sync_main_to_copy(str(main_vault), str(copy_vault), [], [], deleted)
        assert count == 1
        assert copy_vault.joinpath("Notes/OnlyMain.md").exists()
        assert copy_vault.joinpath("Notes/OnlyMain.md").read_text() == main_vault.joinpath("Notes/OnlyMain.md").read_text()

    def test_creates_parent_dirs(self, main_vault, copy_vault):
        _write(main_vault, "Deep/Nested/Note.md", "# Deep note")
        deleted = [("Deep/Nested/Note.md", "# Deep note")]
        count = sync_main_to_copy(str(main_vault), str(copy_vault), [], [], deleted)
        assert count == 1
        assert copy_vault.joinpath("Deep/Nested/Note.md").exists()

    def test_returns_zero_on_empty(self, main_vault, copy_vault):
        count = sync_main_to_copy(str(main_vault), str(copy_vault), [], [], [])
        assert count == 0


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
    def test_poll_pull_failure_surfaces_git_stderr(self, mock_pull):
        mock_pull.side_effect = subprocess.CalledProcessError(
            128,
            ["git", "pull"],
            stderr="fatal: not a git repository",
        )

        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = "/copy"
        svc.poll(main_vault="/main")

        assert svc.last_error == "fatal: not a git repository"
        cs_store.set.assert_not_called()

    @patch("src.clawdy.service.pull")
    @patch("src.clawdy.service.snapshot_vault")
    @patch("src.clawdy.service.diff_vaults")
    @patch("src.clawdy.service.partition_diff")
    @patch("src.clawdy.service.create_clawdy_changeset")
    def test_poll_creates_changeset_on_changes(self, mock_create, mock_partition, mock_diff, mock_snapshot, mock_pull):
        from tests.factories import make_changeset
        mock_cs = make_changeset(source_type="clawdy", items=[], routing=None)
        mock_create.return_value = mock_cs
        mock_pull.return_value = ""
        mock_snapshot.return_value = {}
        mock_diff.return_value = ([], [], [])
        mock_partition.return_value = (([], [], []), ([], [], []))

        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = "/copy"
        svc.poll(main_vault="/main")

        cs_store.set.assert_called_once_with(mock_cs)

    @patch("src.clawdy.service.create_clawdy_changeset")
    @patch("src.clawdy.service.partition_diff")
    @patch("src.clawdy.service.diff_vaults")
    @patch("src.clawdy.service.snapshot_vault")
    @patch("src.clawdy.service.pull")
    def test_poll_merges_when_pending_changeset_exists(
        self,
        mock_pull,
        mock_snapshot,
        mock_diff,
        mock_partition,
        mock_create,
    ):
        from tests.factories import make_changeset

        mock_pull.return_value = ""
        mock_snapshot.return_value = {}
        mock_diff.return_value = ([("Notes/A.md", "main", "copy")], [], [])
        mock_partition.return_value = (([("Notes/A.md", "main", "copy")], [], []), ([], [], []))
        mock_create.return_value = make_changeset(
            source_type="clawdy",
            items=[],
            routing=None,
        )

        settings = MagicMock()
        settings.get.return_value = None
        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([make_changeset()], 1)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = "/copy"
        svc.poll(main_vault="/main")

        mock_pull.assert_called_once_with("/copy")
        cs_store.merge_changes.assert_called_once()
        cs_store.set.assert_not_called()

    @patch("src.clawdy.service.create_clawdy_changeset")
    @patch("src.clawdy.service.partition_diff")
    @patch("src.clawdy.service.diff_vaults")
    @patch("src.clawdy.service.snapshot_vault")
    @patch("src.clawdy.service.sync_main_to_copy")
    @patch("src.clawdy.service.pull")
    def test_poll_clears_stale_pending_changeset_when_no_openclaw_diffs(
        self,
        mock_pull,
        mock_sync_main_to_copy,
        mock_snapshot,
        mock_diff,
        mock_partition,
        mock_create,
    ):
        from tests.factories import make_changeset

        mock_pull.return_value = ""
        mock_sync_main_to_copy.return_value = 1
        mock_snapshot.return_value = {}
        mock_diff.return_value = ([("Notes/A.md", "main", "copy")], [], [])
        mock_partition.return_value = (([], [], []), ([("Notes/A.md", "main", "copy")], [], []))
        mock_create.return_value = None

        settings = MagicMock()
        settings.get.side_effect = lambda key: {
            "clawdy_last_converge": "2026-01-01T00:00:00+00:00",
        }.get(key)
        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([make_changeset()], 1)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = "/copy"
        svc.poll(main_vault="/main")

        cs_store.merge_changes.assert_called_once_with(
            cs_store.get_all_filtered.return_value[0][0].id,
            [],
        )


class TestClawdyServicePollBidirectional:
    @patch("src.clawdy.service.git_push")
    @patch("src.clawdy.service.git_commit")
    @patch("src.clawdy.service.pull")
    def test_auto_syncs_when_converge_exists(self, mock_pull, mock_commit, mock_push, main_vault, copy_vault):
        mock_pull.return_value = ""

        settings = MagicMock()
        settings.get.side_effect = lambda k: {
            "vault_path": str(main_vault),
            "clawdy_last_converge": "2026-01-01T00:00:00+00:00",
        }.get(k)

        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = str(copy_vault)
        svc.poll(main_vault=str(main_vault))

        mock_commit.assert_called_once()
        mock_push.assert_called_once()
        assert svc.last_auto_sync is not None
        assert svc.last_auto_sync > 0

    @patch("src.clawdy.service.pull")
    def test_no_auto_sync_without_converge(self, mock_pull, main_vault, copy_vault):
        mock_pull.return_value = ""

        settings = MagicMock()
        settings.get.side_effect = lambda k: {
            "vault_path": str(main_vault),
            "clawdy_last_converge": None,
        }.get(k)

        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = str(copy_vault)
        svc.poll(main_vault=str(main_vault))

        assert svc.last_auto_sync is None
        cs_store.set.assert_called_once()

    @patch("src.clawdy.service.snapshot_vault")
    @patch("src.clawdy.service.git_push")
    @patch("src.clawdy.service.git_commit")
    @patch("src.clawdy.service.pull")
    def test_auto_sync_push_failure_still_creates_changeset(self, mock_pull, mock_commit, mock_push, mock_snapshot, main_vault, copy_vault):
        mock_pull.return_value = ""
        mock_push.side_effect = Exception("push rejected")
        # Simulate A.md changed during pull (OpenClaw) so it creates a changeset
        mock_snapshot.side_effect = [
            {"Notes/A.md": "pre_hash", "Notes/B.md": "same"},
            {"Notes/A.md": "post_hash", "Notes/B.md": "same"},
        ]

        settings = MagicMock()
        settings.get.side_effect = lambda k: {
            "vault_path": str(main_vault),
            "clawdy_last_converge": "2026-01-01T00:00:00+00:00",
        }.get(k)

        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = str(copy_vault)
        svc.poll(main_vault=str(main_vault))

        assert svc.last_error is not None
        assert "push rejected" in svc.last_error
        # Changeset should still be created despite push failure
        cs_store.set.assert_called_once()

    @patch("src.clawdy.service.git_push")
    @patch("src.clawdy.service.git_commit")
    @patch("src.clawdy.service.pull")
    def test_no_commit_when_zero_synced(self, mock_pull, mock_commit, mock_push, tmp_path):
        vault = tmp_path / "same"
        vault.mkdir()
        (vault / ".obsidian").mkdir()
        _write(vault, "Notes/A.md", "# Same content")

        mock_pull.return_value = ""

        settings = MagicMock()
        settings.get.side_effect = lambda k: {
            "vault_path": str(vault),
            "clawdy_last_converge": "2026-01-01T00:00:00+00:00",
        }.get(k)

        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = str(vault)
        svc.poll(main_vault=str(vault))

        mock_commit.assert_not_called()
        mock_push.assert_not_called()
        assert svc.last_auto_sync == 0
