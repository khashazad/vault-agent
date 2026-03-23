# Bidirectional Clawdy Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-sync user edits from main vault to copy vault so both stay in lockstep.

**Architecture:** Pre/post pull snapshots attribute changes to OpenClaw vs user. OpenClaw changes go to changeset review (existing). User changes auto-sync to copy vault after first convergence (new). Safety guard via `clawdy_last_converge` timestamp in SettingsStore.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (SettingsStore), hashlib, pathlib, React/TypeScript

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `src/clawdy/service.py` | Core sync logic: snapshot, partition, sync, poll | Modify |
| `src/server.py` | Route changes: converge timestamp, config reset, status fields | Modify |
| `src/models/vault.py` | `ClawdyStatusResponse` model | Modify |
| `ui/src/types.ts` | `ClawdyStatus` TypeScript type | Modify |
| `ui/src/pages/ClawdyInboxPage.tsx` | Status bar UI | Modify |
| `tests/unit/test_clawdy_service.py` | Unit tests for new functions + poll changes | Modify |
| `tests/integration/test_clawdy_routes.py` | Integration tests for route changes | Modify |

---

### Task 1: `snapshot_vault` — test + implement

**Files:**
- Modify: `src/clawdy/service.py:1-14` (imports + new function after line 22)
- Test: `tests/unit/test_clawdy_service.py`

- [ ] **Step 1: Write failing tests for `snapshot_vault`**

Add to `tests/unit/test_clawdy_service.py`, after the existing imports:

```python
from src.clawdy.service import snapshot_vault
```

Add new test class after `TestConvergeVaults`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestSnapshotVault -v`
Expected: ImportError — `snapshot_vault` not defined

- [ ] **Step 3: Implement `snapshot_vault`**

In `src/clawdy/service.py`, add `import hashlib` to imports (line 1 area), then add after line 22 (after the type aliases):

```python
# Hash all .md files in a vault directory.
#
# Args:
#     vault_path: Path to the vault.
#
# Returns:
#     Dict mapping relative path to MD5 hex digest.
def snapshot_vault(vault_path: str) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for full_path, rel in iter_markdown_files(vault_path):
        content = full_path.read_bytes()
        hashes[rel] = hashlib.md5(content).hexdigest()
    return hashes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestSnapshotVault -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat(clawdy): add snapshot_vault for md5 hashing vault files"
```

---

### Task 2: `partition_diff` — test + implement

**Files:**
- Modify: `src/clawdy/service.py` (new function after `snapshot_vault`)
- Test: `tests/unit/test_clawdy_service.py`

The type alias for the return value uses the existing `FileChange`, `FileCreate`, `FileDelete` types already defined in `service.py:16-21`.

- [ ] **Step 1: Write failing tests for `partition_diff`**

Add to import in `tests/unit/test_clawdy_service.py`:

```python
from src.clawdy.service import snapshot_vault, partition_diff
```

Add new test class:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestPartitionDiff -v`
Expected: ImportError — `partition_diff` not defined

- [ ] **Step 3: Implement `partition_diff`**

Add after `snapshot_vault` in `src/clawdy/service.py`:

```python
# DiffSet groups the three diff lists into a single tuple.
DiffSet = tuple[list[FileChange], list[FileCreate], list[FileDelete]]


# Split vault diffs into OpenClaw-originated and main-vault-originated.
#
# Args:
#     modified: Modified file tuples from diff_vaults.
#     created: Created file tuples from diff_vaults.
#     deleted: Deleted file tuples from diff_vaults.
#     pull_changed: Set of relative paths that changed during git pull.
#
# Returns:
#     (openclaw_diffs, main_diffs) where each is (modified, created, deleted).
def partition_diff(
    modified: list[FileChange],
    created: list[FileCreate],
    deleted: list[FileDelete],
    pull_changed: set[str],
) -> tuple[DiffSet, DiffSet]:
    oc_mod = [m for m in modified if m[0] in pull_changed]
    oc_cre = [c for c in created if c[0] in pull_changed]
    oc_del = [d for d in deleted if d[0] in pull_changed]

    mn_mod = [m for m in modified if m[0] not in pull_changed]
    mn_cre = [c for c in created if c[0] not in pull_changed]
    mn_del = [d for d in deleted if d[0] not in pull_changed]

    return (oc_mod, oc_cre, oc_del), (mn_mod, mn_cre, mn_del)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestPartitionDiff -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat(clawdy): add partition_diff to attribute changes by origin"
```

---

### Task 3: `sync_main_to_copy` — test + implement

**Files:**
- Modify: `src/clawdy/service.py` (new function after `partition_diff`)
- Test: `tests/unit/test_clawdy_service.py`

- [ ] **Step 1: Write failing tests for `sync_main_to_copy`**

Add to import:

```python
from src.clawdy.service import snapshot_vault, partition_diff, sync_main_to_copy
```

Add new test class:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestSyncMainToCopy -v`
Expected: ImportError — `sync_main_to_copy` not defined

- [ ] **Step 3: Implement `sync_main_to_copy`**

Add after `partition_diff` in `src/clawdy/service.py`:

```python
# Sync user-originated changes from main vault to copy vault.
#
# For modified files, overwrites copy with main content.
# For created (in copy not main), deletes from copy (user deleted from main).
# For deleted (in main not copy), creates in copy from main.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#     modified: Modified file tuples (user-originated only).
#     created: Created file tuples (user-originated only).
#     deleted: Deleted file tuples (user-originated only).
#
# Returns:
#     Number of files synced.
def sync_main_to_copy(
    main_vault: str,
    copy_vault: str,
    modified: list[FileChange],
    created: list[FileCreate],
    deleted: list[FileDelete],
) -> int:
    count = 0

    for rel, _main_content, _copy_content in modified:
        main_file = Path(main_vault, rel)
        copy_file = Path(copy_vault, rel)
        copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")
        count += 1

    for rel, _copy_content in created:
        copy_file = Path(copy_vault, rel)
        if copy_file.exists():
            copy_file.unlink()
            count += 1

    for rel, _main_content in deleted:
        main_file = Path(main_vault, rel)
        copy_file = Path(copy_vault, rel)
        copy_file.parent.mkdir(parents=True, exist_ok=True)
        copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")
        count += 1

    return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestSyncMainToCopy -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat(clawdy): add sync_main_to_copy for bidirectional sync"
```

---

### Task 4: Refactor `create_clawdy_changeset` to accept optional diffs

**Files:**
- Modify: `src/clawdy/service.py:73-122`
- Test: `tests/unit/test_clawdy_service.py`

- [ ] **Step 1: Write failing test for diffs parameter**

Add new test to `TestCreateClawdyChangeset`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestCreateClawdyChangeset::test_uses_provided_diffs tests/unit/test_clawdy_service.py::TestCreateClawdyChangeset::test_provided_empty_diffs_returns_none -v`
Expected: TypeError — unexpected keyword argument `diffs`

- [ ] **Step 3: Refactor `create_clawdy_changeset`**

Change the function signature and first lines in `src/clawdy/service.py`:

```python
# Build a Changeset from vault differences.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#     diffs: Optional pre-computed (modified, created, deleted) tuples. Skips diff_vaults when provided.
#
# Returns:
#     Changeset with one ProposedChange per changed file, or None if no changes.
def create_clawdy_changeset(
    main_vault: str, copy_vault: str, diffs: DiffSet | None = None
) -> Changeset | None:
    if diffs is not None:
        modified, created, deleted = diffs
    else:
        modified, created, deleted = diff_vaults(main_vault, copy_vault)

    if not modified and not created and not deleted:
        return None
```

The rest of the function body (lines 81-122) stays identical.

- [ ] **Step 4: Run ALL existing tests to verify no regression**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: All tests pass (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "refactor(clawdy): add optional diffs param to create_clawdy_changeset"
```

---

### Task 5: Rewrite `ClawdyService.poll()` with bidirectional sync

**Files:**
- Modify: `src/clawdy/service.py:161-243` (ClawdyService class)
- Test: `tests/unit/test_clawdy_service.py`

- [ ] **Step 1: Write failing tests for new poll behavior**

Add imports at top of test file:

```python
from src.clawdy.service import (
    diff_vaults, create_clawdy_changeset, converge_vaults,
    ClawdyService, snapshot_vault, partition_diff, sync_main_to_copy,
)
```

Add new test class:

```python
class TestClawdyServicePollBidirectional:
    @patch("src.clawdy.service.push")
    @patch("src.clawdy.service.commit")
    @patch("src.clawdy.service.pull")
    def test_auto_syncs_when_converge_exists(self, mock_pull, mock_commit, mock_push, main_vault, copy_vault):
        # User edited main vault: changed A.md back to match main, added OnlyMain
        # No pull changes (OpenClaw did nothing)
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

        # Should have committed and pushed auto-sync changes
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
            "clawdy_last_converge": None,  # no convergence yet
        }.get(k)

        cs_store = MagicMock()
        cs_store.get_all_filtered.return_value = ([], 0)

        svc = ClawdyService(settings_store=settings, changeset_store=cs_store)
        svc.enabled = True
        svc.copy_vault_path = str(copy_vault)
        svc.poll(main_vault=str(main_vault))

        # All diffs should go to changeset (no auto-sync)
        assert svc.last_auto_sync is None
        # Changeset should be created with all changes
        cs_store.set.assert_called_once()

    @patch("src.clawdy.service.push")
    @patch("src.clawdy.service.commit")
    @patch("src.clawdy.service.pull")
    def test_auto_sync_push_failure_still_creates_changeset(self, mock_pull, mock_commit, mock_push, main_vault, copy_vault):
        mock_pull.return_value = ""
        mock_push.side_effect = Exception("push rejected")

        # Make copy vault have an OpenClaw change too
        _write(copy_vault, "Notes/A.md", "# A\n\nOpenClaw edit.")

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

        # Push failed but changeset should still be created
        assert svc.last_error is not None
        assert "push rejected" in svc.last_error

    @patch("src.clawdy.service.push")
    @patch("src.clawdy.service.commit")
    @patch("src.clawdy.service.pull")
    def test_no_commit_when_zero_synced(self, mock_pull, mock_commit, mock_push, tmp_path):
        # Both vaults identical — nothing to sync or changeset
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestClawdyServicePollBidirectional -v`
Expected: Failures — `last_auto_sync` attribute missing, old poll logic

- [ ] **Step 3: Implement new poll and update `__init__`**

In `src/clawdy/service.py`, add to imports:

```python
from src.clawdy.git import pull, commit as git_commit, push as git_push
```

(Replace the existing `from src.clawdy.git import pull` line.)

Update `ClawdyService.__init__` to add `last_auto_sync`:

```python
    def __init__(self, settings_store: SettingsStore, changeset_store: ChangesetStore):
        self._settings = settings_store
        self._changeset_store = changeset_store
        self._task: asyncio.Task | None = None
        self.last_poll: str | None = None
        self.last_error: str | None = None
        self.last_auto_sync: int | None = None

        self.copy_vault_path = self._settings.get("clawdy_copy_vault_path")
        interval_str = self._settings.get("clawdy_interval")
        self.interval = int(interval_str) if interval_str else 300
        enabled_str = self._settings.get("clawdy_enabled")
        self.enabled = enabled_str == "true" if enabled_str else False
```

Replace the `poll` method:

```python
    # Run a single poll cycle: snapshot, pull, diff, partition, auto-sync, changeset.
    #
    # Args:
    #     main_vault: Optional override; if None, reads from SettingsStore.
    def poll(self, main_vault: str | None = None) -> None:
        if not self.enabled or not self.copy_vault_path:
            return

        if not main_vault:
            main_vault = self._settings.get("vault_path")
        if not main_vault:
            logger.warning("clawdy: no vault_path configured, skipping poll")
            return

        # Check for pending clawdy changeset
        pending, count = self._changeset_store.get_all_filtered(
            status="pending", source_type="clawdy", limit=1
        )
        if count > 0:
            logger.debug("clawdy: skipping poll, pending changeset exists")
            return

        # Snapshot before pull
        pre_snapshot = snapshot_vault(self.copy_vault_path)

        try:
            pull(self.copy_vault_path)
        except Exception as e:
            self.last_error = str(e)
            logger.warning("clawdy: git pull failed: %s", e)
            return

        # Snapshot after pull
        post_snapshot = snapshot_vault(self.copy_vault_path)

        # Compute which files changed during pull
        pull_changed: set[str] = set()
        all_paths = set(pre_snapshot.keys()) | set(post_snapshot.keys())
        for p in all_paths:
            if pre_snapshot.get(p) != post_snapshot.get(p):
                pull_changed.add(p)

        try:
            logger.info("clawdy: diffing main=%s copy=%s", main_vault, self.copy_vault_path)
            modified, created, deleted = diff_vaults(main_vault, self.copy_vault_path)

            openclaw_diffs, main_diffs = partition_diff(modified, created, deleted, pull_changed)

            # Bidirectional auto-sync (only after first convergence)
            last_converge = self._settings.get("clawdy_last_converge")
            if last_converge:
                mn_mod, mn_cre, mn_del = main_diffs
                if mn_mod or mn_cre or mn_del:
                    sync_count = sync_main_to_copy(
                        main_vault, self.copy_vault_path, mn_mod, mn_cre, mn_del
                    )
                    self.last_auto_sync = sync_count
                    if sync_count > 0:
                        logger.info("clawdy: auto-synced %d files from main to copy", sync_count)
                        try:
                            git_commit(self.copy_vault_path, f"vault-agent: auto-sync {sync_count} user changes")
                            git_push(self.copy_vault_path)
                        except Exception as e:
                            self.last_error = str(e)
                            logger.warning("clawdy: auto-sync commit/push failed: %s", e)
                else:
                    self.last_auto_sync = 0
            else:
                self.last_auto_sync = None
                # No convergence yet — all diffs go to changeset
                openclaw_diffs = (modified, created, deleted)

            cs = create_clawdy_changeset(main_vault, self.copy_vault_path, diffs=openclaw_diffs)
            if cs:
                tools = {}
                for c in cs.changes:
                    tools[c.tool_name] = tools.get(c.tool_name, 0) + 1
                logger.info("clawdy: created changeset %s with %d changes (%s)", cs.id, len(cs.changes), tools)
                self._changeset_store.set(cs)
            self.last_poll = datetime.now(timezone.utc).isoformat()
            # Only clear error if auto-sync didn't set one
            if not last_converge or self.last_auto_sync == 0 or self.last_error is None:
                self.last_error = None
        except Exception as e:
            self.last_error = str(e)
            logger.exception("clawdy: diff/changeset creation failed")
```

- [ ] **Step 4: Run all unit tests**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: All tests pass (existing + new bidirectional tests)

**Note:** The existing `TestClawdyServicePoll` tests mock `create_clawdy_changeset` at module level. After the poll rewrite, they'll also need mocks for `snapshot_vault` and `partition_diff` (or be updated to use real vaults like the new tests). Fix any failures here before committing.

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat(clawdy): rewrite poll() with bidirectional auto-sync"
```

---

### Task 6: Server route changes

**Files:**
- Modify: `src/server.py:1429-1464` (config + status routes), `src/server.py:1508-1520` (converge route)
- Modify: `src/models/vault.py:140-146` (`ClawdyStatusResponse`)
- Test: `tests/integration/test_clawdy_routes.py`

- [ ] **Step 1: Write failing integration tests**

Add to `tests/integration/test_clawdy_routes.py`:

```python
@pytest.mark.asyncio
class TestClawdyBidirectional:
    async def test_converge_sets_last_converge_timestamp(self, client, memory_changeset_store, memory_settings_store, tmp_path):
        from tests.factories import make_changeset, make_proposed_change

        copy_vault = tmp_path / "copy"
        copy_vault.mkdir()
        (copy_vault / ".git").mkdir()
        memory_settings_store.set("clawdy_copy_vault_path", str(copy_vault))

        # Create a fully-resolved clawdy changeset
        change = make_proposed_change(
            tool_name="replace_note",
            input={"path": "Notes/A.md", "content": "new"},
            status="rejected",
        )
        cs = make_changeset(source_type="clawdy", items=[], routing=None, changes=[change])
        memory_changeset_store.set(cs)

        # Mock the clawdy service on the app
        from unittest.mock import MagicMock
        from src.server import app
        mock_svc = MagicMock()
        mock_svc.copy_vault_path = str(copy_vault)
        old_svc = getattr(app.state, "clawdy_service", None)
        import src.server as server_mod
        old_global = server_mod.clawdy_service
        server_mod.clawdy_service = mock_svc

        # Write the file so converge_vaults doesn't error
        note = copy_vault / "Notes"
        note.mkdir(parents=True, exist_ok=True)
        (note / "A.md").write_text("old content")

        from unittest.mock import patch
        with patch("src.server.git_commit"), patch("src.server.git_push"):
            res = await client.post(f"/clawdy/converge/{cs.id}")

        server_mod.clawdy_service = old_global

        assert res.status_code == 200
        assert memory_settings_store.get("clawdy_last_converge") is not None

    async def test_status_includes_bidirectional_fields(self, client):
        res = await client.get("/clawdy/status")
        assert res.status_code == 200
        data = res.json()
        assert "last_auto_sync" in data
        assert "bidirectional_enabled" in data
        assert data["bidirectional_enabled"] is False  # no converge yet

    async def test_config_change_resets_last_converge(self, client, memory_settings_store, tmp_path):
        memory_settings_store.set("clawdy_last_converge", "2026-01-01T00:00:00+00:00")

        new_copy = tmp_path / "new_copy"
        new_copy.mkdir()
        (new_copy / ".git").mkdir()

        await client.put("/clawdy/config", json={"copy_vault_path": str(new_copy)})
        assert memory_settings_store.get("clawdy_last_converge") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_clawdy_routes.py::TestClawdyBidirectional -v`
Expected: Failures — missing fields on response model, no converge timestamp logic

- [ ] **Step 3: Update `ClawdyStatusResponse` model**

In `src/models/vault.py`, update `ClawdyStatusResponse` (line 140):

```python
# Clawdy sync status including poll state and pending changesets.
class ClawdyStatusResponse(BaseModel):
    enabled: bool
    copy_vault_path: str | None
    interval: int
    last_poll: str | None
    last_error: str | None
    pending_changeset_count: int
    last_auto_sync: int | None
    bidirectional_enabled: bool
```

- [ ] **Step 4: Update converge route in `src/server.py`**

After the `git_push` call and before the `# Update changeset status` comment (~line 1510-1515), add:

```python
        git_push(clawdy_service.copy_vault_path)
        get_settings_store().set("clawdy_last_converge", datetime.now(timezone.utc).isoformat())
    except Exception as e:
```

This replaces the existing `git_push` + `except` lines at 1510-1511.

- [ ] **Step 5: Update config route in `src/server.py`**

In `put_clawdy_config` (~line 1434), after `ss.set("clawdy_copy_vault_path", body.copy_vault_path)`, add:

```python
        ss.delete("clawdy_last_converge")
```

- [ ] **Step 6: Update status route in `src/server.py`**

Replace the `get_clawdy_status` return dict (~line 1457-1464) to include new fields:

```python
    return {
        "enabled": clawdy_service.enabled if clawdy_service else False,
        "copy_vault_path": clawdy_service.copy_vault_path if clawdy_service else None,
        "interval": clawdy_service.interval if clawdy_service else 300,
        "last_poll": clawdy_service.last_poll if clawdy_service else None,
        "last_error": clawdy_service.last_error if clawdy_service else None,
        "pending_changeset_count": pending_count,
        "last_auto_sync": clawdy_service.last_auto_sync if clawdy_service else None,
        "bidirectional_enabled": get_settings_store().get("clawdy_last_converge") is not None,
    }
```

- [ ] **Step 7: Run integration tests**

Run: `uv run pytest tests/integration/test_clawdy_routes.py -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add src/models/vault.py src/server.py tests/integration/test_clawdy_routes.py
git commit -m "feat(clawdy): server routes for bidirectional sync (converge timestamp, status fields, config reset)"
```

---

### Task 7: TypeScript type + UI updates

**Files:**
- Modify: `ui/src/types.ts:331-338` (`ClawdyStatus`)
- Modify: `ui/src/pages/ClawdyInboxPage.tsx:116-142` (status bar)

- [ ] **Step 1: Update `ClawdyStatus` in `ui/src/types.ts`**

```typescript
export interface ClawdyStatus {
  enabled: boolean;
  copy_vault_path: string | null;
  interval: number;
  last_poll: string | null;
  last_error: string | null;
  pending_changeset_count: number;
  last_auto_sync: number | null;
  bidirectional_enabled: boolean;
}
```

- [ ] **Step 2: Update status bar in `ClawdyInboxPage.tsx`**

In the status bar `<div>` (after the enabled/disabled span, ~line 117-119), add two new spans:

```tsx
          <span className={status.enabled ? "text-green" : "text-muted"}>
            {status.enabled ? "Enabled" : "Disabled"}
          </span>
          {status.bidirectional_enabled && (
            <span className="text-green">Bidirectional</span>
          )}
          {status.last_auto_sync != null && status.last_auto_sync > 0 && (
            <span>Auto-synced {status.last_auto_sync} files</span>
          )}
```

- [ ] **Step 3: Run frontend tests**

Run: `cd ui && bun run test`
Expected: All pass (no existing tests for ClawdyInboxPage status bar)

- [ ] **Step 4: Commit**

```bash
git add ui/src/types.ts ui/src/pages/ClawdyInboxPage.tsx
git commit -m "feat(clawdy): add bidirectional sync indicator to UI"
```

---

### Task 8: Run full test suite

- [ ] **Step 1: Run all backend tests**

Run: `uv run pytest tests/ -v`
Expected: All pass

- [ ] **Step 2: Run frontend tests**

Run: `cd ui && bun run test`
Expected: All pass

- [ ] **Step 3: Fix any failures, commit fixes**
