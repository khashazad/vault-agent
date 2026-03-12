import pytest

from src.vault import validate_path


class TestValidatePath:
    def test_normal_resolve(self, tmp_vault):
        result = validate_path(str(tmp_vault), "Projects/My Project.md")
        assert result.is_absolute()
        assert "Projects" in str(result)
        assert result.name == "My Project.md"

    def test_traversal_raises(self, tmp_vault):
        with pytest.raises(ValueError, match="escapes the vault"):
            validate_path(str(tmp_vault), "../../../etc/passwd")

    def test_nested_traversal(self, tmp_vault):
        with pytest.raises(ValueError, match="escapes the vault"):
            validate_path(str(tmp_vault), "Projects/../../outside.md")

    def test_simple_path(self, tmp_vault):
        result = validate_path(str(tmp_vault), "note.md")
        expected = tmp_vault / "note.md"
        assert result == expected.resolve()
