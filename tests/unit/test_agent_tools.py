from src.agent.tools import format_search_results, get_tool_definitions
from dataclasses import dataclass


@dataclass
class FakeResult:
    note_path: str
    heading: str
    content: str
    score: float
    search_type: str = "hybrid"


class TestFormatSearchResults:
    def test_formats_results(self):
        results = [
            FakeResult("note.md", "Section", "Some content " * 20, 0.95),
            FakeResult("other.md", "Heading", "Other content " * 20, 0.80),
        ]
        output = format_search_results(results)
        assert "### Result 1 (score: 0.9500)" in output
        assert "### Result 2 (score: 0.8000)" in output
        assert "`note.md`" in output
        assert "`other.md`" in output

    def test_truncates_content(self):
        long_content = "A" * 500
        results = [FakeResult("note.md", "H", long_content, 0.9)]
        output = format_search_results(results)
        # Content should be truncated to 200 chars
        assert len(output.split("\n")[2]) <= 200

    def test_empty_results(self):
        assert format_search_results([]) == ""


class TestGetToolDefinitions:
    def test_returns_correct_tool_count(self):
        tools = get_tool_definitions()
        # 3 base (read, create, update) + search_vault + report_routing_decision = 5
        assert len(tools) == 5

    def test_tool_names(self):
        tools = get_tool_definitions()
        names = {t["name"] for t in tools}
        assert names == {
            "read_note",
            "create_note",
            "update_note",
            "search_vault",
            "report_routing_decision",
        }

    def test_all_tools_have_input_schema(self):
        for tool in get_tool_definitions():
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
