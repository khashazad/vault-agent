from src.agent.changeset import apply_changeset
from tests.factories import make_changeset, make_proposed_change


class TestApplyChangeset:
    def test_apply_approved_create(self, tmp_vault):
        change = make_proposed_change(
            tool_name="create_note",
            input={"path": "Applied/New.md", "content": "# Applied\n\nContent."},
            proposed_content="# Applied\n\nContent.",
            status="approved",
        )
        cs = make_changeset(changes=[change])
        result = apply_changeset(str(tmp_vault), cs)
        assert change.id in result["applied"]
        assert result["failed"] == []
        assert (tmp_vault / "Applied" / "New.md").exists()

    def test_skip_non_approved(self, tmp_vault):
        change = make_proposed_change(status="pending")
        cs = make_changeset(changes=[change])
        result = apply_changeset(str(tmp_vault), cs)
        assert result["applied"] == []

    def test_apply_by_explicit_ids(self, tmp_vault):
        c1 = make_proposed_change(
            tool_name="create_note",
            input={"path": "A.md", "content": "A"},
            status="pending",
        )
        c2 = make_proposed_change(
            tool_name="create_note",
            input={"path": "B.md", "content": "B"},
            status="pending",
        )
        cs = make_changeset(changes=[c1, c2])
        result = apply_changeset(str(tmp_vault), cs, approved_ids=[c1.id])
        assert c1.id in result["applied"]
        assert c2.id not in result["applied"]

    def test_apply_update_note(self, tmp_vault):
        change = make_proposed_change(
            tool_name="update_note",
            input={
                "path": "Projects/My Project.md",
                "operation": "append_section",
                "heading": "References",
                "content": "- [[Applied Ref]]",
            },
            status="approved",
        )
        cs = make_changeset(changes=[change])
        result = apply_changeset(str(tmp_vault), cs)
        assert change.id in result["applied"]
        content = (tmp_vault / "Projects" / "My Project.md").read_text()
        assert "- [[Applied Ref]]" in content

    def test_failed_change_tracked(self, tmp_vault):
        change = make_proposed_change(
            tool_name="create_note",
            input={"path": "Projects/My Project.md", "content": "Dup"},
            status="approved",
        )
        cs = make_changeset(changes=[change])
        result = apply_changeset(str(tmp_vault), cs)
        assert result["applied"] == []
        assert len(result["failed"]) == 1
        assert change.id == result["failed"][0]["id"]
