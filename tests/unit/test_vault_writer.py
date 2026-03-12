from src.models import UpdateNoteInput
from src.vault.writer import compute_update


SAMPLE_NOTE = """---
tags: [ml]
---

# Machine Learning

Overview of ML concepts.

## Key Concepts

- Supervised learning
- Unsupervised learning

## Related

[[Deep Learning]]
"""


class TestComputeUpdate:
    def test_append_under_existing_heading(self):
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            heading="Key Concepts",
            content="- Reinforcement learning",
        )
        result = compute_update(SAMPLE_NOTE, inp)
        # Content should appear between "Key Concepts" and "Related"
        assert "- Reinforcement learning" in result
        # Original content preserved
        assert "- Supervised learning" in result
        assert "## Related" in result

    def test_append_creates_new_heading_if_missing(self):
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            heading="New Section",
            content="New content here.",
        )
        result = compute_update(SAMPLE_NOTE, inp)
        assert "## New Section" in result
        assert "New content here." in result

    def test_append_end_of_file_no_heading(self):
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            content="Appended at the end.",
        )
        result = compute_update(SAMPLE_NOTE, inp)
        assert result.rstrip().endswith("Appended at the end.")

    def test_append_between_same_level_headings(self):
        note = "# Title\n\n## A\n\nContent A.\n\n## B\n\nContent B.\n"
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            heading="A",
            content="Extra under A.",
        )
        result = compute_update(note, inp)
        # Should appear before ## B
        a_pos = result.index("Extra under A.")
        b_pos = result.index("## B")
        assert a_pos < b_pos

    def test_preserves_original_content(self):
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            heading="Key Concepts",
            content="- Transfer learning",
        )
        result = compute_update(SAMPLE_NOTE, inp)
        assert "Overview of ML concepts." in result
        assert "[[Deep Learning]]" in result

    def test_append_under_last_heading(self):
        note = "# Title\n\n## Only Section\n\nSome content.\n"
        inp = UpdateNoteInput(
            path="test.md",
            operation="append_section",
            heading="Only Section",
            content="More content.",
        )
        result = compute_update(note, inp)
        assert "More content." in result
        assert "Some content." in result
