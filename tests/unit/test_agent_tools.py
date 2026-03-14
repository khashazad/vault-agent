from src.agent.tools import get_tool_definitions


class TestGetToolDefinitions:
    def test_returns_correct_tool_count(self):
        tools = get_tool_definitions()
        # 3 base (read, create, update) + report_routing_decision = 4
        assert len(tools) == 4

    def test_tool_names(self):
        tools = get_tool_definitions()
        names = {t["name"] for t in tools}
        assert names == {
            "read_note",
            "create_note",
            "update_note",
            "report_routing_decision",
        }

    def test_all_tools_have_input_schema(self):
        for tool in get_tool_definitions():
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
