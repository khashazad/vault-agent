from src.rag.chunker import chunk_note


class TestChunkNote:
    def test_heading_splits(self):
        content = (
            "## Section A\n\n"
            + ("A content. " * 20)
            + "\n\n## Section B\n\n"
            + ("B content. " * 20)
        )
        chunks = chunk_note("test.md", "Test", content)
        headings = [c.heading for c in chunks]
        assert "Section A" in headings
        assert "Section B" in headings

    def test_preamble_chunk(self):
        content = (
            ("Preamble text. " * 20) + "\n\n## Section\n\n" + ("Section text. " * 20)
        )
        chunks = chunk_note("test.md", "Test Note", content)
        assert chunks[0].heading == "# Test Note"

    def test_min_chunk_chars_threshold(self):
        content = "## Tiny\n\nHi.\n\n## Big\n\n" + ("Long content. " * 20)
        chunks = chunk_note("test.md", "Test", content)
        # "Hi." is below MIN_CHUNK_CHARS, should be excluded
        headings = [c.heading for c in chunks]
        assert "Tiny" not in headings
        assert "Big" in headings

    def test_duplicate_heading_disambiguation(self):
        content = (
            "## Notes\n\n"
            + ("First notes section. " * 20)
            + "\n\n## Notes\n\n"
            + ("Second notes section. " * 20)
        )
        chunks = chunk_note("test.md", "Test", content)
        headings = [c.heading for c in chunks]
        assert "Notes" in headings
        assert "Notes (2)" in headings

    def test_code_fence_stripping(self):
        content = "## Code\n\n```python\nprint('hello')\n```\n\n" + (
            "Explanation text. " * 20
        )
        chunks = chunk_note("test.md", "Test", content)
        for chunk in chunks:
            assert "```" not in chunk.content

    def test_latex_stripping(self):
        content = "## Math\n\n$$E = mc^2$$\n\n" + ("Explanation text. " * 20)
        chunks = chunk_note("test.md", "Test", content)
        for chunk in chunks:
            assert "$$" not in chunk.content

    def test_no_headings_returns_single_chunk(self):
        content = "Just a plain note with enough text. " * 20
        chunks = chunk_note("test.md", "Plain", content)
        assert len(chunks) == 1
        assert chunks[0].heading == "# Plain"

    def test_empty_content(self):
        assert chunk_note("test.md", "Empty", "") == []

    def test_content_hash_present(self):
        content = "## Section\n\n" + ("Content. " * 20)
        chunks = chunk_note("test.md", "Test", content)
        assert all(len(c.content_hash) == 32 for c in chunks)  # MD5 hex

    def test_note_path_preserved(self):
        content = "## Section\n\n" + ("Content. " * 20)
        chunks = chunk_note("Papers/test.md", "Test", content)
        assert all(c.note_path == "Papers/test.md" for c in chunks)
