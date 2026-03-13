import pytest
from pydantic import ValidationError

from src.models import (
    Changeset,
    ChangeContentUpdate,
    ChangesetListResponse,
    ChangesetSummary,
    ContentItem,
    FeedbackRequest,
    UpdateNoteInput,
)
from tests.factories import make_content_item, make_routing_info


class TestChangesetMigration:
    def test_highlights_to_items_migration(self):
        """Old persisted changesets used 'highlights' key — should migrate to 'items'."""
        data = {
            "id": "test-id",
            "highlights": [make_content_item().model_dump()],
            "changes": [],
            "reasoning": "test",
            "status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
        }
        cs = Changeset.model_validate(data)
        assert len(cs.items) == 1
        assert cs.source_type == "web"  # default

    def test_items_field_preferred_over_highlights(self):
        data = {
            "id": "test-id",
            "items": [make_content_item().model_dump()],
            "changes": [],
            "reasoning": "test",
            "status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
        }
        cs = Changeset.model_validate(data)
        assert len(cs.items) == 1


class TestContentItem:
    def test_max_length_text(self):
        with pytest.raises(ValidationError):
            ContentItem(text="x" * 50_001, source="test")

    def test_valid_source_types(self):
        for st in ("web", "zotero", "book"):
            item = make_content_item(source_type=st)
            assert item.source_type == st

    def test_invalid_source_type(self):
        with pytest.raises(ValidationError):
            ContentItem(text="test", source="test", source_type="invalid")


class TestChangesetStatus:
    def test_revision_requested_status_accepted(self):
        data = {
            "id": "test-id",
            "items": [make_content_item().model_dump()],
            "changes": [],
            "reasoning": "test",
            "status": "revision_requested",
            "created_at": "2024-01-01T00:00:00Z",
        }
        cs = Changeset.model_validate(data)
        assert cs.status == "revision_requested"


class TestFeedbackRequest:
    def test_valid(self):
        req = FeedbackRequest(feedback="Please change the heading")
        assert req.feedback == "Please change the heading"

    def test_empty_allowed(self):
        req = FeedbackRequest(feedback="")
        assert req.feedback == ""


class TestChangeContentUpdate:
    def test_status_only(self):
        update = ChangeContentUpdate(status="approved")
        assert update.status == "approved"
        assert update.proposed_content is None

    def test_content_only(self):
        update = ChangeContentUpdate(proposed_content="# New content")
        assert update.proposed_content == "# New content"
        assert update.status is None

    def test_both(self):
        update = ChangeContentUpdate(status="approved", proposed_content="# New")
        assert update.status == "approved"
        assert update.proposed_content == "# New"


class TestChangesetSummary:
    def test_valid(self):
        summary = ChangesetSummary(
            id="cs-1",
            status="pending",
            created_at="2024-01-01T00:00:00Z",
            source_type="web",
            change_count=2,
            routing=make_routing_info(),
            feedback=None,
            parent_changeset_id=None,
        )
        assert summary.change_count == 2

    def test_with_feedback(self):
        summary = ChangesetSummary(
            id="cs-1",
            status="revision_requested",
            created_at="2024-01-01T00:00:00Z",
            source_type="zotero",
            change_count=1,
            routing=None,
            feedback="Fix the heading",
            parent_changeset_id="cs-0",
        )
        assert summary.feedback == "Fix the heading"
        assert summary.parent_changeset_id == "cs-0"


class TestChangesetListResponse:
    def test_valid(self):
        resp = ChangesetListResponse(changesets=[], total=0)
        assert resp.total == 0
        assert resp.changesets == []


class TestUpdateNoteInput:
    def test_heading_optional(self):
        inp = UpdateNoteInput(path="test.md", operation="append_section")
        assert inp.heading is None
        assert inp.content is None

    def test_with_heading_and_content(self):
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            heading="Notes",
            content="New content.",
        )
        assert inp.heading == "Notes"
        assert inp.content == "New content."
