from src.agent.diff import generate_diff


class TestGenerateDiff:
    def test_new_file_all_additions(self):
        diff = generate_diff("note.md", "", "# Title\n\nContent.\n")
        assert "+# Title" in diff
        assert "+Content." in diff
        assert "--- a/note.md" in diff
        assert "+++ b/note.md" in diff

    def test_modify_mixed_changes(self):
        original = "Line 1\nLine 2\nLine 3\n"
        proposed = "Line 1\nModified 2\nLine 3\nLine 4\n"
        diff = generate_diff("note.md", original, proposed)
        assert "-Line 2" in diff
        assert "+Modified 2" in diff
        assert "+Line 4" in diff

    def test_identical_returns_empty(self):
        content = "Same content.\n"
        diff = generate_diff("note.md", content, content)
        assert diff == ""

    def test_diff_header_paths(self):
        diff = generate_diff("Papers/Test.md", "", "Content.\n")
        assert "a/Papers/Test.md" in diff
        assert "b/Papers/Test.md" in diff
