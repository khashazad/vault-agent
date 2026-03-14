from src.agent.prompts import (
    build_zotero_synthesis_prompt,
    get_color_label,
)
from tests.factories import make_zotero_content_item


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


class TestBuildZoteroSynthesisPrompt:
    def test_returns_system_and_user(self):
        items = [make_zotero_content_item()]
        meta = items[0].source_metadata
        system, user = build_zotero_synthesis_prompt(items, meta)
        assert "research note synthesizer" in system
        assert "Paper Context" in user
        assert meta.title in user

    def test_synthesis_framing(self):
        items = [make_zotero_content_item()]
        meta = items[0].source_metadata
        system, user = build_zotero_synthesis_prompt(items, meta)
        assert "analytical summary" in system
        assert "synthesize" in system.lower()
        assert "analytical summary" in user

    def test_no_old_formatting(self):
        items = [make_zotero_content_item()]
        meta = items[0].source_metadata
        system, _ = build_zotero_synthesis_prompt(items, meta)
        assert "ad-abstract" not in system
        assert "ad-quote" not in system
        assert "- !" not in system
        assert "- =" not in system

    def test_feedback_included(self):
        items = [make_zotero_content_item()]
        meta = items[0].source_metadata
        _, user = build_zotero_synthesis_prompt(
            items,
            meta,
            feedback="Use a different structure.",
            previous_reasoning="I structured the note by topic.",
        )
        assert "Previous Attempt" in user
        assert "Use a different structure." in user
        assert "I structured the note by topic." in user

    def test_no_feedback_when_none(self):
        items = [make_zotero_content_item()]
        meta = items[0].source_metadata
        _, user = build_zotero_synthesis_prompt(items, meta)
        assert "Previous Attempt" not in user
