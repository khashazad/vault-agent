import pytest

from src.models import CreateNoteInput, UpdateNoteInput
from src.vault.writer import create_note, update_note


class TestCreateNote:
    def test_creates_file(self, tmp_vault):
        inp = CreateNoteInput(path="New/Note.md", content="# New Note\n\nContent.")
        result = create_note(str(tmp_vault), inp)
        assert "Created" in result
        assert (tmp_vault / "New" / "Note.md").exists()
        assert (tmp_vault / "New" / "Note.md").read_text() == "# New Note\n\nContent."

    def test_creates_parent_dirs(self, tmp_vault):
        inp = CreateNoteInput(path="Deep/Nested/Dir/Note.md", content="# Deep")
        create_note(str(tmp_vault), inp)
        assert (tmp_vault / "Deep" / "Nested" / "Dir" / "Note.md").exists()

    def test_fails_on_existing_file(self, tmp_vault):
        inp = CreateNoteInput(path="Projects/My Project.md", content="# Overwrite")
        with pytest.raises(FileExistsError):
            create_note(str(tmp_vault), inp)


class TestUpdateNote:
    def test_append_to_existing(self, tmp_vault):
        inp = UpdateNoteInput(
            path="Projects/My Project.md",
            operation="append_section",
            heading="References",
            content="- [[New Reference]]",
        )
        result = update_note(str(tmp_vault), inp)
        assert "Appended" in result
        content = (tmp_vault / "Projects" / "My Project.md").read_text()
        assert "- [[New Reference]]" in content

    def test_append_creates_heading(self, tmp_vault):
        inp = UpdateNoteInput(
            path="Projects/My Project.md",
            operation="append_section",
            heading="New Section",
            content="New content here.",
        )
        update_note(str(tmp_vault), inp)
        content = (tmp_vault / "Projects" / "My Project.md").read_text()
        assert "## New Section" in content
        assert "New content here." in content

    def test_fails_on_missing_note(self, tmp_vault):
        inp = UpdateNoteInput(
            path="Nonexistent.md",
            operation="append_section",
            content="Will fail.",
        )
        with pytest.raises(FileNotFoundError):
            update_note(str(tmp_vault), inp)
