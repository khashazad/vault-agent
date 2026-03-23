# Clawdy Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate an external agent (OpenClaw) that pushes changes to a git-tracked copy vault, surfaced as reviewable changesets in the vault-agent UI.

**Architecture:** A `ClawdyService` polls the copy vault (git pull + full-state diff against main vault), creates `Changeset` objects through the existing pipeline, and converges both vaults after review. New `replace_note` and `delete_note` operations extend the write layer. A dedicated "Clawdy Inbox" page provides config, status, and changeset listing.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (WAL), subprocess (git), React 19, TypeScript, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-22-clawdy-inbox-design.md`

---

## File Map

### New files

| File | Responsibility |
|------|---------------|
| `src/clawdy/__init__.py` | Module exports |
| `src/clawdy/git.py` | Thin subprocess wrapper for git pull/commit/push/status |
| `src/clawdy/service.py` | Poll loop, vault diffing, changeset creation, convergence |
| `ui/src/pages/ClawdyInboxPage.tsx` | Status/config panel + filtered changeset list |
| `tests/unit/test_clawdy_git.py` | Git wrapper unit tests |
| `tests/unit/test_clawdy_service.py` | Diff logic, changeset creation, convergence tests |
| `tests/integration/test_clawdy_routes.py` | API endpoint integration tests |
| `tests/integration/test_clawdy_apply.py` | replace_note/delete_note through apply_changeset |

### Modified files

| File | Changes |
|------|---------|
| `src/models/content.py` | Add `"clawdy"` to `SourceType` literal |
| `src/models/changesets.py` | Add tool_name values, make `items` default to `[]` |
| `src/models/tools.py` | Add `ReplaceNoteInput`, `DeleteNoteInput` |
| `src/models/__init__.py` | Re-export new models |
| `src/vault/writer.py` | Add `replace_note()`, `delete_note()` |
| `src/agent/changeset.py` | Handle `replace_note`, `delete_note` in apply |
| `src/db/changesets.py` | Add `source_type` column, filter support |
| `src/server.py` | Add `/clawdy/*` routes, lifespan hook, `source_type` param on `GET /changesets` |
| `src/config.py` | No changes needed (config from SettingsStore at runtime) |
| `tests/factories.py` | Add `make_replace_change()`, `make_delete_change()` |
| `ui/src/types.ts` | Add `ClawdyConfig`, `ClawdyStatus`, update `SourceType` |
| `ui/src/api/client.ts` | Add clawdy API functions, `source_type` param on `fetchChangesets` |
| `ui/src/router.tsx` | Add `/clawdy` route |
| `ui/src/components/Sidebar.tsx` | Add "Clawdy Inbox" nav item |
| `ui/src/pages/ChangesetDetailPage.tsx` | Add "Finalize & Sync" button for clawdy changesets |

---

## Task 1: Model Layer Changes

**Files:**
- Modify: `src/models/content.py:5`
- Modify: `src/models/changesets.py:49,66`
- Modify: `src/models/tools.py`
- Modify: `src/models/__init__.py`
- Test: `tests/unit/test_models.py`

- [ ] **Step 1: Write test for SourceType accepting "clawdy"**

In `tests/unit/test_models.py`, add:

```python
from src.models import ContentItem, Changeset, ProposedChange
from tests.factories import make_changeset, make_proposed_change


def test_source_type_accepts_clawdy():
    item = ContentItem(text="test", source="test", source_type="clawdy")
    assert item.source_type == "clawdy"


def test_changeset_clawdy_defaults():
    cs = make_changeset(source_type="clawdy", items=[], routing=None)
    assert cs.source_type == "clawdy"
    assert cs.items == []
    assert cs.routing is None


def test_changeset_items_defaults_to_empty():
    cs = make_changeset(items=None)
    assert cs.items == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_models.py::test_source_type_accepts_clawdy tests/unit/test_models.py::test_changeset_clawdy_defaults tests/unit/test_models.py::test_changeset_items_defaults_to_empty -v`
Expected: FAIL — "clawdy" not in SourceType literal, items has no default

- [ ] **Step 3: Update SourceType in content.py**

In `src/models/content.py`, change:
```python
SourceType = Literal["web", "zotero", "book", "clawdy"]
```

- [ ] **Step 4: Make Changeset.items optional with default**

In `src/models/changesets.py`, change the `items` field on `Changeset`:
```python
    items: list[ContentItem] = Field(
        default_factory=list,
        description="Content items that produced this changeset"
    )
```

- [ ] **Step 5: Write test for new tool_name values on ProposedChange**

In `tests/unit/test_models.py`, add:

```python
def test_proposed_change_replace_note():
    pc = make_proposed_change(
        tool_name="replace_note",
        input={"path": "Notes/test.md", "content": "new content"},
        original_content="old content",
        proposed_content="new content",
    )
    assert pc.tool_name == "replace_note"


def test_proposed_change_delete_note():
    pc = make_proposed_change(
        tool_name="delete_note",
        input={"path": "Notes/test.md"},
        original_content="old content",
        proposed_content="",
    )
    assert pc.tool_name == "delete_note"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_models.py::test_proposed_change_replace_note tests/unit/test_models.py::test_proposed_change_delete_note -v`
Expected: FAIL — "replace_note" not in Literal

- [ ] **Step 7: Update ProposedChange.tool_name**

In `src/models/changesets.py`, change:
```python
    tool_name: Literal["create_note", "update_note", "replace_note", "delete_note"] = Field(
        description="Which write operation to perform"
    )
```

- [ ] **Step 8: Add ReplaceNoteInput and DeleteNoteInput**

In `src/models/tools.py`, add:
```python
class ReplaceNoteInput(BaseModel):
    path: str = Field(max_length=500)
    content: str = Field(max_length=200_000)


class DeleteNoteInput(BaseModel):
    path: str = Field(max_length=500)
```

- [ ] **Step 9: Update models/__init__.py**

In `src/models/__init__.py`, add imports and __all__ entries for `ReplaceNoteInput` and `DeleteNoteInput`.

- [ ] **Step 10: Update factories.py**

In `tests/factories.py`, update the `make_changeset` default to handle `items=None`:
```python
def make_changeset(**overrides) -> Changeset:
    defaults = {
        "id": str(uuid.uuid4()),
        "items": [make_content_item()],
        "changes": [make_proposed_change()],
        "reasoning": "Created a new note for this content.",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_type": "web",
        "routing": make_routing_info(),
    }
    defaults.update(overrides)
    if defaults["items"] is None:
        del defaults["items"]
    return Changeset(**defaults)
```

Add factory helpers:
```python
def make_replace_change(**overrides) -> ProposedChange:
    defaults = {
        "id": str(uuid.uuid4()),
        "tool_name": "replace_note",
        "input": {"path": "Notes/Test.md", "content": "# Updated\n\nNew content."},
        "original_content": "# Test\n\nOld content.",
        "proposed_content": "# Updated\n\nNew content.",
        "diff": "--- a/Notes/Test.md\n+++ b/Notes/Test.md\n@@ -1,3 +1,3 @@\n-# Test\n+# Updated\n \n-Old content.\n+New content.\n",
        "status": "pending",
    }
    defaults.update(overrides)
    return ProposedChange(**defaults)


def make_delete_change(**overrides) -> ProposedChange:
    defaults = {
        "id": str(uuid.uuid4()),
        "tool_name": "delete_note",
        "input": {"path": "Notes/Obsolete.md"},
        "original_content": "# Obsolete\n\nOld content.",
        "proposed_content": "",
        "diff": "--- a/Notes/Obsolete.md\n+++ b/Notes/Obsolete.md\n@@ -1,3 +0,0 @@\n-# Obsolete\n-\n-Old content.\n",
        "status": "pending",
    }
    defaults.update(overrides)
    return ProposedChange(**defaults)
```

- [ ] **Step 11: Run all model tests**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add src/models/ tests/unit/test_models.py tests/factories.py
git commit -m "feat: extend models for clawdy — SourceType, tool_names, input models"
```

---

## Task 2: Vault Writer — replace_note and delete_note

**Files:**
- Modify: `src/vault/writer.py`
- Test: `tests/unit/test_vault_writer.py`

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_vault_writer.py`, add:

```python
from src.vault.writer import replace_note, delete_note


class TestReplaceNote:
    def test_replaces_existing_file(self, tmp_vault):
        vault = str(tmp_vault)
        path = "Projects/My Project.md"
        new_content = "# Replaced\n\nNew content."
        result = replace_note(vault, path, new_content)
        assert "Replaced" in result
        full = tmp_vault / path
        assert full.read_text() == new_content

    def test_raises_on_missing_file(self, tmp_vault):
        import pytest
        with pytest.raises(FileNotFoundError):
            replace_note(str(tmp_vault), "Nonexistent.md", "content")

    def test_rejects_path_traversal(self, tmp_vault):
        import pytest
        with pytest.raises(ValueError, match="escapes"):
            replace_note(str(tmp_vault), "../outside.md", "content")


class TestDeleteNote:
    def test_deletes_existing_file(self, tmp_vault):
        vault = str(tmp_vault)
        path = "daily/2024-01-01.md"
        result = delete_note(vault, path)
        assert "Deleted" in result
        assert not (tmp_vault / path).exists()

    def test_raises_on_missing_file(self, tmp_vault):
        import pytest
        with pytest.raises(FileNotFoundError):
            delete_note(str(tmp_vault), "Nonexistent.md")

    def test_rejects_path_traversal(self, tmp_vault):
        import pytest
        with pytest.raises(ValueError, match="escapes"):
            delete_note(str(tmp_vault), "../outside.md")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_vault_writer.py::TestReplaceNote tests/unit/test_vault_writer.py::TestDeleteNote -v`
Expected: FAIL — functions don't exist

- [ ] **Step 3: Implement replace_note and delete_note**

In `src/vault/writer.py`, add:

```python
# Overwrite an existing note with new content.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     note_path: Relative path to the note within the vault.
#     content: New file content.
#
# Returns:
#     Confirmation message.
#
# Raises:
#     FileNotFoundError: When the target note does not exist.
#     ValueError: When the path escapes the vault directory.
def replace_note(vault_path: str, note_path: str, content: str) -> str:
    full_path = validate_path(vault_path, note_path)
    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")
    full_path.write_text(content, encoding="utf-8")
    return f"Replaced note at {note_path}"


# Delete an existing note from the vault.
#
# Args:
#     vault_path: Absolute path to the Obsidian vault root.
#     note_path: Relative path to the note within the vault.
#
# Returns:
#     Confirmation message.
#
# Raises:
#     FileNotFoundError: When the target note does not exist.
#     ValueError: When the path escapes the vault directory.
def delete_note(vault_path: str, note_path: str) -> str:
    full_path = validate_path(vault_path, note_path)
    if not full_path.exists():
        raise FileNotFoundError(f"Note not found: {note_path}")
    full_path.unlink()
    return f"Deleted note at {note_path}"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_vault_writer.py::TestReplaceNote tests/unit/test_vault_writer.py::TestDeleteNote -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/vault/writer.py tests/unit/test_vault_writer.py
git commit -m "feat: add replace_note and delete_note to vault writer"
```

---

## Task 3: Extend apply_changeset

**Files:**
- Modify: `src/agent/changeset.py`
- Test: `tests/integration/test_clawdy_apply.py` (new)

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/test_clawdy_apply.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_clawdy_apply.py -v`
Expected: FAIL — apply_changeset doesn't handle replace_note/delete_note

- [ ] **Step 3: Extend apply_changeset**

In `src/agent/changeset.py`, add imports and handlers:

```python
from src.models import Changeset, CreateNoteInput, UpdateNoteInput, ReplaceNoteInput, DeleteNoteInput
from src.vault.writer import create_note, update_note, replace_note, delete_note


def apply_changeset(
    vault_path: str,
    changeset: Changeset,
    approved_ids: list[str] | None = None,
) -> dict:
    applied: list[str] = []
    failed: list[dict] = []

    for change in changeset.changes:
        if approved_ids is not None:
            if change.id not in approved_ids:
                continue
        elif change.status != "approved":
            continue

        try:
            if change.tool_name == "create_note":
                inp = CreateNoteInput(**change.input)
                create_note(vault_path, inp)
                applied.append(change.id)

            elif change.tool_name == "update_note":
                inp = UpdateNoteInput(**change.input)
                update_note(vault_path, inp)
                applied.append(change.id)

            elif change.tool_name == "replace_note":
                inp = ReplaceNoteInput(**change.input)
                replace_note(vault_path, inp.path, inp.content)
                applied.append(change.id)

            elif change.tool_name == "delete_note":
                inp = DeleteNoteInput(**change.input)
                delete_note(vault_path, inp.path)
                applied.append(change.id)

            change.status = "applied"

        except Exception as err:
            failed.append({"id": change.id, "error": str(err)})

    return {"applied": applied, "failed": failed}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_clawdy_apply.py -v`
Expected: PASS

- [ ] **Step 5: Run existing changeset tests to verify no regressions**

Run: `uv run pytest tests/integration/test_changeset_apply.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agent/changeset.py tests/integration/test_clawdy_apply.py
git commit -m "feat: extend apply_changeset with replace_note and delete_note"
```

---

## Task 4: ChangesetStore source_type Filtering

**Files:**
- Modify: `src/db/changesets.py`
- Test: `tests/integration/test_store.py`

- [ ] **Step 1: Write failing test**

In `tests/integration/test_store.py`, add:

```python
def test_changeset_store_filter_by_source_type(memory_changeset_store):
    from tests.factories import make_changeset
    store = memory_changeset_store

    cs_web = make_changeset(source_type="web")
    cs_clawdy = make_changeset(source_type="clawdy", items=[], routing=None)
    store.set(cs_web)
    store.set(cs_clawdy)

    results, total = store.get_all_filtered(source_type="clawdy")
    assert total == 1
    assert results[0].id == cs_clawdy.id

    results, total = store.get_all_filtered(source_type="web")
    assert total == 1
    assert results[0].id == cs_web.id

    results, total = store.get_all_filtered()
    assert total == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_store.py::test_changeset_store_filter_by_source_type -v`
Expected: FAIL — `get_all_filtered` doesn't accept source_type

- [ ] **Step 3: Add source_type column and filtering**

In `src/db/changesets.py`, update `_create_table` to add the column and backfill:

```python
    def _create_table(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS changesets (
                id         TEXT PRIMARY KEY,
                status     TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                data       TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'web'
            );
            CREATE INDEX IF NOT EXISTS idx_changesets_status
                ON changesets(status);
            CREATE INDEX IF NOT EXISTS idx_changesets_created_at
                ON changesets(created_at);
            CREATE INDEX IF NOT EXISTS idx_changesets_source_type
                ON changesets(source_type);
        """)
        self._conn.commit()
        self._maybe_add_source_type_column()

    # Add source_type column to existing tables and backfill from JSON data.
    def _maybe_add_source_type_column(self) -> None:
        cols = [
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(changesets)").fetchall()
        ]
        if "source_type" not in cols:
            self._conn.execute(
                "ALTER TABLE changesets ADD COLUMN source_type TEXT NOT NULL DEFAULT 'web'"
            )
            self._conn.execute(
                "UPDATE changesets SET source_type = json_extract(data, '$.source_type') "
                "WHERE json_extract(data, '$.source_type') IS NOT NULL"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_changesets_source_type ON changesets(source_type)"
            )
            self._conn.commit()
```

Update `set()` to populate `source_type`:

```python
    def set(self, changeset: Changeset) -> None:
        self._conn.execute(
            """
            INSERT INTO changesets (id, status, created_at, data, source_type)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                data   = excluded.data,
                source_type = excluded.source_type
            """,
            (
                changeset.id,
                changeset.status,
                changeset.created_at,
                changeset.model_dump_json(),
                changeset.source_type,
            ),
        )
        self._conn.commit()
```

Update `get_all_filtered` signature:

```python
    def get_all_filtered(
        self,
        status: str | None = None,
        offset: int = 0,
        limit: int = 25,
        source_type: str | None = None,
    ) -> tuple[list[Changeset], int]:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if source_type:
            conditions.append("source_type = ?")
            params.append(source_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        total = self._conn.execute(
            f"SELECT COUNT(*) as cnt FROM changesets {where}", params
        ).fetchone()["cnt"]
        rows = self._conn.execute(
            f"SELECT data FROM changesets {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [Changeset.model_validate_json(r["data"]) for r in rows], total
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/integration/test_store.py::test_changeset_store_filter_by_source_type -v`
Expected: PASS

- [ ] **Step 5: Run all store tests for regressions**

Run: `uv run pytest tests/integration/test_store.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/db/changesets.py tests/integration/test_store.py
git commit -m "feat: add source_type column and filtering to ChangesetStore"
```

---

## Task 5: Git Wrapper

**Files:**
- Create: `src/clawdy/__init__.py`
- Create: `src/clawdy/git.py`
- Test: `tests/unit/test_clawdy_git.py` (new)

- [ ] **Step 1: Create module init**

Create `src/clawdy/__init__.py`:
```python
```

- [ ] **Step 2: Write failing tests for git wrapper**

Create `tests/unit/test_clawdy_git.py`:

```python
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.clawdy.git import pull, commit, push, is_git_repo, status


class TestIsGitRepo:
    def test_valid_git_repo(self, tmp_path):
        (tmp_path / ".git").mkdir()
        assert is_git_repo(str(tmp_path)) is True

    def test_not_a_git_repo(self, tmp_path):
        assert is_git_repo(str(tmp_path)) is False

    def test_nonexistent_path(self):
        assert is_git_repo("/nonexistent/path") is False


class TestPull:
    @patch("src.clawdy.git.subprocess.run")
    def test_pull_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.\n")
        result = pull(str(tmp_path))
        assert result == "Already up to date.\n"
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0] == ["git", "pull"]
        assert args[1]["cwd"] == str(tmp_path)

    @patch("src.clawdy.git.subprocess.run")
    def test_pull_failure_raises(self, mock_run, tmp_path):
        mock_run.side_effect = subprocess.CalledProcessError(1, "git pull", stderr="error")
        with pytest.raises(subprocess.CalledProcessError):
            pull(str(tmp_path))


class TestCommit:
    @patch("src.clawdy.git.subprocess.run")
    def test_commit_stages_and_commits(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        commit(str(tmp_path), "test message")
        assert mock_run.call_count == 2
        add_call = mock_run.call_args_list[0]
        assert add_call[0][0] == ["git", "add", "-A"]
        commit_call = mock_run.call_args_list[1]
        assert "test message" in commit_call[0][0]


class TestPush:
    @patch("src.clawdy.git.subprocess.run")
    def test_push_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        push(str(tmp_path))
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["git", "push"]


class TestStatus:
    @patch("src.clawdy.git.subprocess.run")
    def test_status_returns_output(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout=" M file.md\n")
        result = status(str(tmp_path))
        assert result == " M file.md\n"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_git.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 4: Implement git.py**

Create `src/clawdy/git.py`:

```python
import subprocess
from pathlib import Path


# Check if a directory is a git repository.
#
# Args:
#     repo_path: Filesystem path to check.
#
# Returns:
#     True if .git directory exists, False otherwise.
def is_git_repo(repo_path: str) -> bool:
    return Path(repo_path, ".git").is_dir()


# Pull latest changes from the remote.
#
# Args:
#     repo_path: Path to the git repository.
#
# Returns:
#     Stdout from git pull.
#
# Raises:
#     subprocess.CalledProcessError: If git pull fails.
def pull(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "pull"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


# Stage all changes and commit with a message.
#
# Args:
#     repo_path: Path to the git repository.
#     message: Commit message.
#
# Raises:
#     subprocess.CalledProcessError: If git add or commit fails.
def commit(repo_path: str, message: str) -> None:
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )


# Push local commits to the remote.
#
# Args:
#     repo_path: Path to the git repository.
#
# Raises:
#     subprocess.CalledProcessError: If git push fails.
def push(repo_path: str) -> None:
    subprocess.run(
        ["git", "push"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )


# Get the porcelain status of the repository.
#
# Args:
#     repo_path: Path to the git repository.
#
# Returns:
#     Output of git status --porcelain.
def status(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_clawdy_git.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/clawdy/ tests/unit/test_clawdy_git.py
git commit -m "feat: add git subprocess wrapper for clawdy"
```

---

## Task 6: ClawdyService — Diffing and Changeset Creation

**Files:**
- Create: `src/clawdy/service.py`
- Test: `tests/unit/test_clawdy_service.py` (new)

- [ ] **Step 1: Write failing tests for diff_vaults**

Create `tests/unit/test_clawdy_service.py`:

```python
from pathlib import Path

import pytest

from src.clawdy.service import diff_vaults, create_clawdy_changeset


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement diff_vaults and create_clawdy_changeset**

Create `src/clawdy/service.py`:

```python
import logging
import uuid
from datetime import datetime, timezone

from src.agent.diff import generate_diff
from src.models import Changeset, ProposedChange
from src.vault import iter_markdown_files

logger = logging.getLogger("vault-agent")

# File change tuple: (relative_path, main_content, copy_content)
FileChange = tuple[str, str, str]
# Delete tuple: (relative_path, main_content)
FileDelete = tuple[str, str]
# Create tuple: (relative_path, copy_content)
FileCreate = tuple[str, str]


# Diff all .md files between main vault and copy vault.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#
# Returns:
#     Tuple of (modified, created, deleted) file lists.
def diff_vaults(
    main_vault: str, copy_vault: str
) -> tuple[list[FileChange], list[FileCreate], list[FileDelete]]:
    main_files: dict[str, str] = {}
    for _, rel in iter_markdown_files(main_vault):
        from pathlib import Path
        content = Path(main_vault, rel).read_text(encoding="utf-8")
        main_files[rel] = content

    copy_files: dict[str, str] = {}
    for _, rel in iter_markdown_files(copy_vault):
        from pathlib import Path
        content = Path(copy_vault, rel).read_text(encoding="utf-8")
        copy_files[rel] = content

    modified: list[FileChange] = []
    created: list[FileCreate] = []
    deleted: list[FileDelete] = []

    # Files in copy but not main = created
    # Files in both but different = modified
    for rel, copy_content in copy_files.items():
        if rel not in main_files:
            created.append((rel, copy_content))
        elif copy_content != main_files[rel]:
            modified.append((rel, main_files[rel], copy_content))

    # Files in main but not copy = deleted
    for rel, main_content in main_files.items():
        if rel not in copy_files:
            deleted.append((rel, main_content))

    return modified, created, deleted


# Build a Changeset from vault differences.
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#
# Returns:
#     Changeset with one ProposedChange per changed file, or None if no changes.
def create_clawdy_changeset(
    main_vault: str, copy_vault: str
) -> Changeset | None:
    modified, created, deleted = diff_vaults(main_vault, copy_vault)

    if not modified and not created and not deleted:
        return None

    changes: list[ProposedChange] = []

    for rel, original, proposed in modified:
        diff = generate_diff(rel, original, proposed)
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="replace_note",
            input={"path": rel, "content": proposed},
            original_content=original,
            proposed_content=proposed,
            diff=diff,
        ))

    for rel, content in created:
        diff = generate_diff(rel, "", content)
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="create_note",
            input={"path": rel, "content": content},
            original_content=None,
            proposed_content=content,
            diff=diff,
        ))

    for rel, original in deleted:
        diff = generate_diff(rel, original, "")
        changes.append(ProposedChange(
            id=str(uuid.uuid4()),
            tool_name="delete_note",
            input={"path": rel},
            original_content=original,
            proposed_content="",
            diff=diff,
        ))

    return Changeset(
        id=str(uuid.uuid4()),
        changes=changes,
        reasoning="Changes detected from OpenClaw sync",
        source_type="clawdy",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat: add vault diff and changeset creation for clawdy"
```

---

## Task 7: ClawdyService — Convergence

**Files:**
- Modify: `src/clawdy/service.py`
- Test: `tests/unit/test_clawdy_service.py`

- [ ] **Step 1: Write failing tests for converge**

In `tests/unit/test_clawdy_service.py`, add:

```python
from src.clawdy.service import converge_vaults


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestConvergeVaults -v`
Expected: FAIL — function doesn't exist

- [ ] **Step 3: Implement converge_vaults**

In `src/clawdy/service.py`, add:

```python
from pathlib import Path


# Sync the copy vault to match the main vault for rejected changes.
#
# For rejected changes, overwrites copy vault files with main vault content.
# For applied changes, no action needed (main vault already updated).
#
# Args:
#     main_vault: Path to the main vault.
#     copy_vault: Path to the copy vault.
#     changes_map: Dict of {relative_path: {"tool_name": str, "status": str}}.
def converge_vaults(
    main_vault: str,
    copy_vault: str,
    changes_map: dict[str, dict[str, str]],
) -> None:
    for rel_path, info in changes_map.items():
        if info["status"] != "rejected":
            continue

        main_file = Path(main_vault, rel_path)
        copy_file = Path(copy_vault, rel_path)

        if info["tool_name"] == "replace_note":
            # Rejected modification: restore main's version in copy
            copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")

        elif info["tool_name"] == "create_note":
            # Rejected creation: delete from copy
            if copy_file.exists():
                copy_file.unlink()

        elif info["tool_name"] == "delete_note":
            # Rejected deletion: restore file in copy from main
            copy_file.parent.mkdir(parents=True, exist_ok=True)
            copy_file.write_text(main_file.read_text(encoding="utf-8"), encoding="utf-8")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestConvergeVaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat: add convergence logic for clawdy rejected changes"
```

---

## Task 8: ClawdyService — Poll Loop

**Files:**
- Modify: `src/clawdy/service.py`
- Test: `tests/unit/test_clawdy_service.py`

- [ ] **Step 1: Write tests for ClawdyService class**

In `tests/unit/test_clawdy_service.py`, add:

```python
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from src.clawdy.service import ClawdyService


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_clawdy_service.py::TestClawdyServiceInit tests/unit/test_clawdy_service.py::TestClawdyServicePoll -v`
Expected: FAIL — ClawdyService class doesn't exist

- [ ] **Step 3: Implement ClawdyService**

In `src/clawdy/service.py`, add:

```python
from src.clawdy.git import pull
from src.db.changesets import ChangesetStore
from src.db.settings import SettingsStore


# Background service that polls the copy vault and creates changesets.
class ClawdyService:
    # Initialize from SettingsStore config.
    #
    # Args:
    #     settings_store: SettingsStore for reading config.
    #     changeset_store: ChangesetStore for persisting changesets.
    def __init__(self, settings_store: SettingsStore, changeset_store: ChangesetStore):
        self._settings = settings_store
        self._changeset_store = changeset_store
        self._task: asyncio.Task | None = None
        self.last_poll: str | None = None
        self.last_error: str | None = None

        self.copy_vault_path = self._settings.get("clawdy_copy_vault_path")
        interval_str = self._settings.get("clawdy_interval")
        self.interval = int(interval_str) if interval_str else 300
        enabled_str = self._settings.get("clawdy_enabled")
        self.enabled = enabled_str == "true" if enabled_str else False

    # Run a single poll cycle: pull, diff, create changeset.
    #
    # Args:
    #     main_vault: Path to the main vault.
    def poll(self, main_vault: str) -> None:
        if not self.enabled or not self.copy_vault_path:
            return

        # Check for pending clawdy changeset
        pending, count = self._changeset_store.get_all_filtered(
            status="pending", source_type="clawdy", limit=1
        )
        if count > 0:
            logger.debug("clawdy: skipping poll, pending changeset exists")
            return

        try:
            pull(self.copy_vault_path)
        except Exception as e:
            self.last_error = str(e)
            logger.warning("clawdy: git pull failed: %s", e)
            return

        try:
            cs = create_clawdy_changeset(main_vault, self.copy_vault_path)
            if cs:
                self._changeset_store.set(cs)
                logger.info("clawdy: created changeset %s with %d changes", cs.id, len(cs.changes))
            self.last_error = None
            self.last_poll = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            self.last_error = str(e)
            logger.exception("clawdy: diff/changeset creation failed")

    # Start the background poll loop.
    #
    # Args:
    #     main_vault: Path to the main vault.
    async def start(self, main_vault: str) -> None:
        self._task = asyncio.create_task(self._poll_loop(main_vault))

    # Stop the background poll loop.
    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self, main_vault: str) -> None:
        while True:
            try:
                self.poll(main_vault)
            except Exception:
                logger.exception("clawdy: unexpected error in poll loop")
            await asyncio.sleep(self.interval)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_clawdy_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/clawdy/service.py tests/unit/test_clawdy_service.py
git commit -m "feat: add ClawdyService with poll loop and config loading"
```

---

## Task 9: Server Routes

**Files:**
- Modify: `src/server.py`
- Test: `tests/integration/test_clawdy_routes.py` (new)

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/test_clawdy_routes.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport

import src.db as db_module
from src.db import ChangesetStore, SettingsStore
from src.server import app


@pytest.fixture
def memory_settings_store():
    s = SettingsStore(db_path=":memory:")
    old = db_module._settings_store
    db_module._settings_store = s
    yield s
    db_module._settings_store = old
    s.close()


@pytest.fixture
def memory_changeset_store():
    s = ChangesetStore(db_path=":memory:")
    old = db_module._changeset_store
    db_module._changeset_store = s
    yield s
    db_module._changeset_store = old
    s.close()


@pytest.fixture
async def client(tmp_vault, app_config, memory_settings_store, memory_changeset_store):
    app.state.config = app_config
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestClawdyConfig:
    async def test_get_config_defaults(self, client):
        res = await client.get("/clawdy/config")
        assert res.status_code == 200
        data = res.json()
        assert data["copy_vault_path"] is None
        assert data["interval"] == 300
        assert data["enabled"] is False

    async def test_put_config(self, client, tmp_path, memory_settings_store):
        copy_vault = tmp_path / "copy"
        copy_vault.mkdir()
        (copy_vault / ".git").mkdir()

        res = await client.put("/clawdy/config", json={
            "copy_vault_path": str(copy_vault),
            "interval": 60,
            "enabled": True,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["copy_vault_path"] == str(copy_vault)
        assert data["interval"] == 60
        assert data["enabled"] is True

    async def test_put_config_invalid_path(self, client):
        res = await client.put("/clawdy/config", json={
            "copy_vault_path": "/nonexistent/path",
        })
        assert res.status_code == 400


@pytest.mark.asyncio
class TestClawdyStatus:
    async def test_get_status(self, client):
        res = await client.get("/clawdy/status")
        assert res.status_code == 200
        data = res.json()
        assert "enabled" in data
        assert "last_poll" in data
        assert "pending_changeset_count" in data


@pytest.mark.asyncio
class TestChangesetSourceTypeFilter:
    async def test_filter_by_source_type(self, client, memory_changeset_store):
        from tests.factories import make_changeset
        cs_web = make_changeset(source_type="web")
        cs_clawdy = make_changeset(source_type="clawdy", items=[], routing=None)
        memory_changeset_store.set(cs_web)
        memory_changeset_store.set(cs_clawdy)

        res = await client.get("/changesets?source_type=clawdy")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["changesets"][0]["source_type"] == "clawdy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_clawdy_routes.py -v`
Expected: FAIL — routes don't exist

- [ ] **Step 3: Add Clawdy Pydantic models for requests/responses**

In `src/models/vault.py` or a new section at bottom of `src/server.py`, add the request/response models. Prefer keeping them in models — add to `src/models/vault.py`:

```python
class ClawdyConfigRequest(BaseModel):
    copy_vault_path: str | None = None
    interval: int | None = None
    enabled: bool | None = None

class ClawdyConfigResponse(BaseModel):
    copy_vault_path: str | None
    interval: int
    enabled: bool

class ClawdyStatusResponse(BaseModel):
    enabled: bool
    copy_vault_path: str | None
    interval: int
    last_poll: str | None
    last_error: str | None
    pending_changeset_count: int
```

Update `src/models/__init__.py` and `src/models/vault.py` to export these.

- [ ] **Step 4: Add server routes and lifespan hook**

In `src/server.py`:

Add to imports:
```python
from src.clawdy.service import ClawdyService
from src.clawdy.git import is_git_repo
```

Add module-level variable:
```python
clawdy_service: ClawdyService | None = None
```

Update `lifespan` to start ClawdyService:
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global paper_cache_syncer, clawdy_service
    if not hasattr(app.state, "config"):
        app.state.config = load_config()
    config = app.state.config
    logger.info("vault: %s", config.vault_path or "not configured")
    zotero_ok = bool(config.zotero_api_key and config.zotero_library_id)
    logger.info("zotero: %s", "configured" if zotero_ok else "not configured")
    if zotero_ok and config.vault_path:
        paper_cache_syncer = ZoteroPaperCacheSyncer(config)
        paper_cache_syncer.start()
    # Start clawdy service
    clawdy_service = ClawdyService(
        settings_store=get_settings_store(),
        changeset_store=get_changeset_store(),
    )
    if clawdy_service.enabled and config.vault_path:
        await clawdy_service.start(config.vault_path)
        logger.info("clawdy: polling started (interval=%ds)", clawdy_service.interval)
    yield
    if clawdy_service:
        clawdy_service.stop()
    if paper_cache_syncer is not None:
        paper_cache_syncer.stop()
```

Add `source_type` param to `list_changesets`:
```python
async def list_changesets(
    status: str | None = None,
    offset: int = 0,
    limit: int = 25,
    source_type: str | None = None,
):
    changesets, total = get_changeset_store().get_all_filtered(
        status, offset, limit, source_type=source_type
    )
```

Add clawdy routes:
```python
# Get clawdy sync configuration.
@app.get("/clawdy/config", tags=["Clawdy"])
async def get_clawdy_config():
    ss = get_settings_store()
    return {
        "copy_vault_path": ss.get("clawdy_copy_vault_path"),
        "interval": int(ss.get("clawdy_interval") or "300"),
        "enabled": ss.get("clawdy_enabled") == "true",
    }


# Update clawdy sync configuration.
@app.put("/clawdy/config", tags=["Clawdy"])
async def put_clawdy_config(body: ClawdyConfigRequest):
    ss = get_settings_store()

    if body.copy_vault_path is not None:
        if not Path(body.copy_vault_path).is_dir():
            raise HTTPException(400, "Path does not exist")
        if not is_git_repo(body.copy_vault_path):
            raise HTTPException(400, "Path is not a git repository")
        ss.set("clawdy_copy_vault_path", body.copy_vault_path)
        if clawdy_service:
            clawdy_service.copy_vault_path = body.copy_vault_path

    if body.interval is not None:
        ss.set("clawdy_interval", str(body.interval))
        if clawdy_service:
            clawdy_service.interval = body.interval

    if body.enabled is not None:
        ss.set("clawdy_enabled", "true" if body.enabled else "false")
        if clawdy_service:
            clawdy_service.enabled = body.enabled

    return await get_clawdy_config()


# Get clawdy sync status.
@app.get("/clawdy/status", tags=["Clawdy"])
async def get_clawdy_status():
    _, pending_count = get_changeset_store().get_all_filtered(
        status="pending", source_type="clawdy", limit=0
    )
    return {
        "enabled": clawdy_service.enabled if clawdy_service else False,
        "copy_vault_path": clawdy_service.copy_vault_path if clawdy_service else None,
        "interval": clawdy_service.interval if clawdy_service else 300,
        "last_poll": clawdy_service.last_poll if clawdy_service else None,
        "last_error": clawdy_service.last_error if clawdy_service else None,
        "pending_changeset_count": pending_count,
    }


# Manually trigger a clawdy poll cycle.
@app.post("/clawdy/trigger", tags=["Clawdy"])
async def trigger_clawdy_sync(request: Request):
    _require_vault(request)
    if not clawdy_service or not clawdy_service.copy_vault_path:
        raise HTTPException(400, "Clawdy not configured")
    config = _get_config(request)
    clawdy_service.poll(config.vault_path)
    return {"status": "ok", "last_poll": clawdy_service.last_poll}


# Run convergence on a fully-resolved clawdy changeset.
@app.post("/clawdy/converge/{changeset_id}", tags=["Clawdy"])
async def converge_clawdy(changeset_id: str, request: Request):
    _require_vault(request)
    cs = _get_changeset_or_404(changeset_id)
    if cs.source_type != "clawdy":
        raise HTTPException(400, "Not a clawdy changeset")

    # Check all changes are in terminal state
    for change in cs.changes:
        if change.status not in ("applied", "rejected"):
            raise HTTPException(400, f"Change {change.id} is still {change.status}")

    config = _get_config(request)
    if not clawdy_service or not clawdy_service.copy_vault_path:
        raise HTTPException(400, "Clawdy not configured")

    from src.clawdy.service import converge_vaults
    from src.clawdy.git import commit as git_commit, push as git_push

    changes_map = {}
    for change in cs.changes:
        path = change.input.get("path", "")
        changes_map[path] = {"tool_name": change.tool_name, "status": change.status}

    converge_vaults(config.vault_path, clawdy_service.copy_vault_path, changes_map)

    # Build commit message
    applied = sum(1 for c in cs.changes if c.status == "applied")
    rejected = sum(1 for c in cs.changes if c.status == "rejected")
    paths = [c.input.get("path", "") for c in cs.changes]
    message = f"vault-agent: applied {applied}, rejected {rejected} changes\n\n" + "\n".join(f"- {p}" for p in paths)

    try:
        git_commit(clawdy_service.copy_vault_path, message)
        git_push(clawdy_service.copy_vault_path)
    except Exception as e:
        logger.warning("clawdy: convergence commit/push failed: %s", e)
        raise HTTPException(500, f"Convergence git operation failed: {e}")

    # Update changeset status
    has_applied = any(c.status == "applied" for c in cs.changes)
    cs.status = "applied" if has_applied else "rejected"
    get_changeset_store().set(cs)

    return {"id": cs.id, "status": cs.status}
```

Import `ClawdyConfigRequest` in the server imports block.

- [ ] **Step 5: Run integration tests**

Run: `uv run pytest tests/integration/test_clawdy_routes.py -v`
Expected: PASS

- [ ] **Step 6: Run all existing server route tests for regressions**

Run: `uv run pytest tests/integration/test_server_routes.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/server.py src/models/vault.py src/models/__init__.py tests/integration/test_clawdy_routes.py
git commit -m "feat: add /clawdy/* server routes and source_type filter on /changesets"
```

---

## Task 10: Frontend Types and API Client

**Files:**
- Modify: `ui/src/types.ts`
- Modify: `ui/src/api/client.ts`

- [ ] **Step 1: Update SourceType and add Clawdy types**

In `ui/src/types.ts`, update:

```typescript
export type SourceType = "web" | "zotero" | "book" | "clawdy";
```

Add at the bottom:

```typescript
// --- Clawdy types ---

export interface ClawdyConfig {
  copy_vault_path: string | null;
  interval: number;
  enabled: boolean;
}

export interface ClawdyStatus {
  enabled: boolean;
  copy_vault_path: string | null;
  interval: number;
  last_poll: string | null;
  last_error: string | null;
  pending_changeset_count: number;
}
```

- [ ] **Step 2: Add source_type param to fetchChangesets and add clawdy API functions**

In `ui/src/api/client.ts`, update `fetchChangesets`:

```typescript
export function fetchChangesets(opts?: {
  status?: string;
  offset?: number;
  limit?: number;
  source_type?: string;
}): Promise<ChangesetListResponse> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.offset) params.set("offset", String(opts.offset));
  if (opts?.limit) params.set("limit", String(opts.limit));
  if (opts?.source_type) params.set("source_type", opts.source_type);
  const qs = params.toString();
  return fetchJSON(`${BASE}/changesets${qs ? `?${qs}` : ""}`);
}
```

Add clawdy functions:

```typescript
// --- Clawdy API ---

export function fetchClawdyConfig(): Promise<ClawdyConfig> {
  return fetchJSON(`${BASE}/clawdy/config`);
}

export function updateClawdyConfig(
  config: Partial<ClawdyConfig>,
): Promise<ClawdyConfig> {
  return fetchJSON(`${BASE}/clawdy/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
}

export function fetchClawdyStatus(): Promise<ClawdyStatus> {
  return fetchJSON(`${BASE}/clawdy/status`);
}

export function triggerClawdySync(): Promise<{ status: string; last_poll: string }> {
  return fetchJSON(`${BASE}/clawdy/trigger`, { method: "POST" });
}

export function convergeClawdy(
  changesetId: string,
): Promise<{ id: string; status: string }> {
  return fetchJSON(`${BASE}/clawdy/converge/${changesetId}`, {
    method: "POST",
  });
}
```

Add imports for `ClawdyConfig`, `ClawdyStatus` from `../types`.

- [ ] **Step 3: Commit**

```bash
git add ui/src/types.ts ui/src/api/client.ts
git commit -m "feat: add clawdy types and API client functions"
```

---

## Task 11: ClawdyInboxPage

**Files:**
- Create: `ui/src/pages/ClawdyInboxPage.tsx`
- Modify: `ui/src/router.tsx`
- Modify: `ui/src/components/Sidebar.tsx`

- [ ] **Step 1: Create ClawdyInboxPage**

Create `ui/src/pages/ClawdyInboxPage.tsx`. The page has two sections:

1. **Config/status bar** at top: copy vault path, enable toggle, interval picker, sync status, "Check Now" button
2. **Changeset list** below: fetches `source_type=clawdy` changesets, renders like `ChangesetsPage`

Reference `ChangesetsPage.tsx` for the changeset card pattern and reuse `StatusBadge`, `Pagination`, `ErrorAlert`, `Skeleton`.

The page should:
- On mount: fetch config + status + changesets
- "Check Now" button: calls `triggerClawdySync()`, then reloads status + changesets
- Enable/disable toggle: calls `updateClawdyConfig({ enabled: !enabled })`
- Interval selector: dropdown with 60/300/900/1800 values
- Changeset cards navigate to `/changesets/:id`
- Show `last_poll` timestamp, `last_error` if present, `pending_changeset_count`

- [ ] **Step 2: Add route to router.tsx**

In `ui/src/router.tsx`, add import and route:

```typescript
import { ClawdyInboxPage } from "./pages/ClawdyInboxPage";
```

Add to children array:
```typescript
{ path: "clawdy", element: <ClawdyInboxPage /> },
```

- [ ] **Step 3: Add sidebar nav item**

In `ui/src/components/Sidebar.tsx`, add to `NAV_ITEMS` array (after "Changesets"):

```typescript
{
  to: "/clawdy",
  label: "Clawdy Inbox",
  icon: (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect width="20" height="16" x="2" y="4" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  ),
},
```

- [ ] **Step 4: Run frontend tests for regressions**

Run: `cd ui && bun run test`
Expected: PASS (existing tests should not break)

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages/ClawdyInboxPage.tsx ui/src/router.tsx ui/src/components/Sidebar.tsx
git commit -m "feat: add ClawdyInboxPage with config, status, and changeset list"
```

---

## Task 12: ChangesetDetailPage — Finalize & Sync Button

**Files:**
- Modify: `ui/src/pages/ChangesetDetailPage.tsx`

- [ ] **Step 1: Add convergence button for clawdy changesets**

In `ui/src/pages/ChangesetDetailPage.tsx`:

Import `convergeClawdy` from api client.

Add state:
```typescript
const [converging, setConverging] = useState(false);
```

Add handler:
```typescript
const handleConverge = useCallback(async () => {
  if (!changesetId) return;
  setConverging(true);
  setError(null);
  try {
    await convergeClawdy(changesetId);
    const cs = await fetchChangeset(changesetId);
    setDetail(cs);
  } catch (err) {
    setError(formatError(err));
  } finally {
    setConverging(false);
  }
}, [changesetId]);
```

Compute whether convergence is available:
```typescript
const isClawdy = detail?.source_type === "clawdy";
const allResolved = detail?.changes.every(
  (c) => c.status === "applied" || c.status === "rejected"
);
const showConverge = isClawdy && allResolved && detail?.status !== "applied" && detail?.status !== "rejected";
```

Render the button in the header bar, near the delete button:
```tsx
{showConverge && (
  <button
    onClick={handleConverge}
    disabled={converging}
    className="text-xs bg-green/15 text-green border border-green/30 rounded px-3 py-1 cursor-pointer hover:bg-green/25 disabled:opacity-50 disabled:cursor-not-allowed"
  >
    {converging ? "Syncing..." : "Finalize & Sync"}
  </button>
)}
```

Also update `backToList` for clawdy changesets to navigate to `/clawdy` instead of `/changesets`:
```typescript
function backToList() {
  if (detail?.source_type === "clawdy") {
    navigate("/clawdy");
  } else {
    navigate("/changesets");
  }
}
```

- [ ] **Step 2: Run frontend tests**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/ChangesetDetailPage.tsx
git commit -m "feat: add Finalize & Sync button for clawdy changesets"
```

---

## Task 13: Full Integration Test Pass

- [ ] **Step 1: Run all backend tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 2: Run all frontend tests**

Run: `cd ui && bun run test`
Expected: PASS

- [ ] **Step 3: Fix any failures, then commit**

```bash
git add -A
git commit -m "fix: resolve test failures from clawdy integration"
```

(Only if there were fixes needed)

---

## Task 14: Update CLAUDE.md

- [ ] **Step 1: Add clawdy to CLAUDE.md documentation**

Update relevant sections:
- Add `src/clawdy/` to Key Modules
- Add `/clawdy/*` to API Endpoints
- Add `/clawdy` to Router structure
- Add `ClawdyInboxPage` to Pages
- Update File Structure tree
- Mention the write policy expansion (replace_note, delete_note scoped to clawdy)

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add clawdy inbox to CLAUDE.md"
```
