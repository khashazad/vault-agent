"""Test data factories for building valid model instances with sensible defaults."""

import uuid
from datetime import datetime, timezone

from src.models import (
    Changeset,
    ContentItem,
    ProposedChange,
    RoutingInfo,
    SourceMetadata,
)


def make_content_item(**overrides) -> ContentItem:
    defaults = {
        "text": "This is a highlighted passage about neural networks.",
        "source": "https://example.com/article",
        "annotation": None,
        "source_type": "web",
        "color": None,
        "source_metadata": None,
    }
    defaults.update(overrides)
    return ContentItem(**defaults)


def make_zotero_content_item(**overrides) -> ContentItem:
    defaults = {
        "text": "The model achieves state-of-the-art results on ImageNet.",
        "source": "Deep Learning Paper",
        "annotation": "Key result",
        "source_type": "zotero",
        "color": "#ffd400",
        "source_metadata": SourceMetadata(
            title="Deep Learning for Computer Vision",
            doi="10.1234/test.2024",
            authors=["Smith, John", "Doe, Jane"],
            year="2024",
            paper_key="ABC123",
        ),
    }
    defaults.update(overrides)
    return ContentItem(**defaults)


def make_proposed_change(**overrides) -> ProposedChange:
    defaults = {
        "id": str(uuid.uuid4()),
        "tool_name": "create_note",
        "input": {"path": "Papers/Test Note.md", "content": "# Test\n\nContent."},
        "original_content": None,
        "proposed_content": "# Test\n\nContent.",
        "diff": "--- a/Papers/Test Note.md\n+++ b/Papers/Test Note.md\n@@ -0,0 +1,3 @@\n+# Test\n+\n+Content.\n",
        "status": "pending",
    }
    defaults.update(overrides)
    return ProposedChange(**defaults)


def make_routing_info(**overrides) -> RoutingInfo:
    defaults = {
        "action": "create",
        "target_path": "Papers/Test Note.md",
        "reasoning": "No existing note covers this topic.",
        "confidence": 0.9,
    }
    defaults.update(overrides)
    return RoutingInfo(**defaults)


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
