from src.agent.prompts import (
    build_system_prompt,
    build_user_message,
    build_batch_user_message,
    build_zotero_synthesis_prompt,
    get_color_label,
    SOURCE_CONFIGS,
)
from tests.factories import make_content_item, make_zotero_content_item


class TestGetColorLabel:
    def test_known_colors(self):
        assert get_color_label("#ff6666") == "Critical"
        assert get_color_label("#ffd400") == "Important"
        assert get_color_label("#5fb236") == "General"

    def test_case_insensitive(self):
        assert get_color_label("#FFD400") == "Important"

    def test_unknown_color(self):
        assert get_color_label("#000000") is None

    def test_none_color(self):
        assert get_color_label(None) is None


class TestBuildSystemPrompt:
    def test_vault_map_interpolation(self):
        vault_map = "## Vault Summary (42 notes)\n\n### Folder Structure\n  Root/ (5 notes)"
        prompt = build_system_prompt(vault_map, SOURCE_CONFIGS["web"])
        assert "42 notes" in prompt
        assert "Root/ (5 notes)" in prompt

    def test_source_type_terminology_web(self):
        prompt = build_system_prompt("vault map", SOURCE_CONFIGS["web"])
        assert "highlight" in prompt.lower()

    def test_source_type_terminology_zotero(self):
        prompt = build_system_prompt("vault map", SOURCE_CONFIGS["zotero"], source_type="zotero")
        assert "annotation" in prompt.lower()
        assert "Paper Note Template" in prompt

    def test_batch_mode_includes_batch_section(self):
        prompt = build_system_prompt("vault map", SOURCE_CONFIGS["web"], is_batch=True)
        assert "Batch Processing" in prompt

    def test_contains_tool_descriptions(self):
        prompt = build_system_prompt("vault map", SOURCE_CONFIGS["web"])
        assert "search_vault" in prompt
        assert "report_routing_decision" in prompt
        assert "create_note" in prompt
        assert "update_note" in prompt


class TestBuildUserMessage:
    def test_basic_message(self):
        item = make_content_item()
        msg = build_user_message(item, SOURCE_CONFIGS["web"])
        assert item.text in msg
        assert item.source in msg

    def test_annotation_included(self):
        item = make_content_item(annotation="My note about this.")
        msg = build_user_message(item, SOURCE_CONFIGS["web"])
        assert "My note about this." in msg

    def test_color_label_included(self):
        item = make_content_item(color="#ff6666")
        msg = build_user_message(item, SOURCE_CONFIGS["web"])
        assert "Critical" in msg

    def test_feedback_section(self):
        item = make_content_item()
        msg = build_user_message(
            item, SOURCE_CONFIGS["web"],
            feedback="Wrong note, put it elsewhere.",
            previous_reasoning="I chose to update Note X.",
        )
        assert "Previous Attempt" in msg
        assert "Wrong note" in msg

    def test_search_context_included(self):
        item = make_content_item()
        msg = build_user_message(
            item, SOURCE_CONFIGS["web"],
            search_context="### Result 1 (score: 0.85)\n**Note:** `test.md` > Heading\nSnippet...",
        )
        assert "Vault Search Results" in msg
        assert "score: 0.85" in msg


class TestBuildBatchUserMessage:
    def test_single_item_delegates(self):
        item = make_content_item()
        msg = build_batch_user_message([item], SOURCE_CONFIGS["web"])
        assert "integrate this highlight" in msg.lower()

    def test_multi_item_batch(self):
        items = [make_content_item(text=f"Highlight {i}") for i in range(3)]
        msg = build_batch_user_message(items, SOURCE_CONFIGS["web"])
        assert "3 highlights" in msg
        for i in range(3):
            assert f"Highlight {i}" in msg


class TestBuildZoteroSynthesisPrompt:
    def test_returns_system_and_user(self):
        items = [make_zotero_content_item()]
        meta = items[0].source_metadata
        system, user = build_zotero_synthesis_prompt(items, meta)
        assert "research note synthesizer" in system
        assert "Paper Context" in user
        assert meta.title in user
