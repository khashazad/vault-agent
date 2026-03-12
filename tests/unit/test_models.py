import pytest
from pydantic import ValidationError

from src.models import Changeset, ContentItem, UpdateNoteInput
from tests.factories import make_content_item


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
