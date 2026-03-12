from src.vault.reader import build_vault_map


class TestBuildVaultMap:
    def test_counts_notes(self, tmp_vault):
        vm = build_vault_map(str(tmp_vault))
        assert vm.total_notes == 4  # 4 sample notes in conftest

    def test_note_summaries(self, tmp_vault):
        vm = build_vault_map(str(tmp_vault))
        paths = [n.path for n in vm.notes]
        assert "Projects/My Project.md" in paths
        assert "Topics/Machine Learning.md" in paths

    def test_wikilinks_extracted(self, tmp_vault):
        vm = build_vault_map(str(tmp_vault))
        project = next(n for n in vm.notes if n.path == "Projects/My Project.md")
        assert "Machine Learning" in project.wikilinks

    def test_headings_extracted(self, tmp_vault):
        vm = build_vault_map(str(tmp_vault))
        project = next(n for n in vm.notes if n.path == "Projects/My Project.md")
        assert "Overview" in project.headings
        assert "References" in project.headings

    def test_as_string_format(self, tmp_vault):
        vm = build_vault_map(str(tmp_vault))
        assert "Vault Summary" in vm.as_string
        assert "4 notes" in vm.as_string

    def test_skips_dotfiles(self, tmp_vault):
        # .obsidian/ should be skipped
        vm = build_vault_map(str(tmp_vault))
        paths = [n.path for n in vm.notes]
        assert not any(".obsidian" in p for p in paths)
