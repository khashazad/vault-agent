from datetime import datetime, timezone

import pytest

from src.agent.diff import generate_diff
from src.db.changesets import ChangesetStore
from src.models import Changeset, ProposedChange


# Build a ProposedChange for merge_changes() tests.
def make_change(
    path: str,
    original: str = "old",
    proposed: str = "new",
    **overrides,
) -> ProposedChange:
    return ProposedChange(
        id=overrides.get("id", f"ch-{path}"),
        tool_name=overrides.get("tool_name", "replace_note"),
        input=overrides.get("input", {"path": path, "content": proposed}),
        original_content=original,
        proposed_content=proposed,
        diff=overrides.get("diff", generate_diff(path, original, proposed)),
        status=overrides.get("status", "pending"),
    )


# Build a minimal Changeset for merge_changes() tests.
def make_changeset(changes: list[ProposedChange], **overrides) -> Changeset:
    now = datetime.now(timezone.utc).isoformat()
    return Changeset(
        id=overrides.get("id", "cs-1"),
        changes=changes,
        reasoning=overrides.get("reasoning", "test"),
        source_type=overrides.get("source_type", "clawdy"),
        created_at=overrides.get("created_at", now),
        updated_at=overrides.get("updated_at", now),
    )


@pytest.fixture
def store():
    changeset_store = ChangesetStore(":memory:")
    yield changeset_store
    changeset_store.close()


# merge_changes() store behavior.
class TestMergeChanges:
    def test_updates_existing_path_and_preserves_id(self, store):
        store.set(make_changeset([make_change("a.md", "old", "v1")]))

        result = store.merge_changes(
            "cs-1",
            [make_change("a.md", "old", "v2", id="new-change-id", status="approved")],
        )

        assert result is not None
        assert len(result.changes) == 1
        assert result.changes[0].id == "ch-a.md"
        assert result.changes[0].proposed_content == "v2"
        assert result.changes[0].status == "pending"

    def test_adds_new_paths(self, store):
        store.set(make_changeset([make_change("a.md")]))

        result = store.merge_changes("cs-1", [make_change("a.md"), make_change("b.md")])

        assert result is not None
        assert {change.input["path"] for change in result.changes} == {"a.md", "b.md"}

    def test_removes_paths_missing_from_new_set(self, store):
        store.set(make_changeset([make_change("a.md"), make_change("b.md")]))

        result = store.merge_changes("cs-1", [make_change("a.md")])

        assert result is not None
        assert len(result.changes) == 1
        assert result.changes[0].input["path"] == "a.md"

    def test_deletes_changeset_when_merge_result_is_empty(self, store):
        store.set(make_changeset([make_change("a.md")]))

        result = store.merge_changes("cs-1", [])

        assert result is None
        assert store.get("cs-1") is None

    def test_updates_updated_at_timestamp(self, store):
        changeset = make_changeset([make_change("a.md")])
        store.set(changeset)

        result = store.merge_changes("cs-1", [make_change("a.md", "old", "v2")])

        assert result is not None
        assert result.updated_at is not None
        assert result.updated_at != changeset.updated_at

    def test_returns_none_for_missing_changeset(self, store):
        assert store.merge_changes("missing", [make_change("a.md")]) is None
