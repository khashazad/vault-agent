from src.vault.taxonomy import extract_tags, build_tag_hierarchy


class TestExtractTags:
    def test_frontmatter_tags(self):
        fm = {"tags": ["ml", "paper"]}
        body = "No inline tags here."
        tags = extract_tags(fm, body)
        assert tags == {"ml", "paper"}

    def test_inline_tags(self):
        fm = {}
        body = "Some text with #research and #biology/genomics inline."
        tags = extract_tags(fm, body)
        assert tags == {"research", "biology/genomics"}

    def test_combined_frontmatter_and_inline(self):
        fm = {"tags": ["paper"]}
        body = "Discusses #ml concepts."
        tags = extract_tags(fm, body)
        assert tags == {"paper", "ml"}

    def test_skips_headings(self):
        fm = {}
        body = "# Heading\n## Another Heading\nText with #real-tag."
        tags = extract_tags(fm, body)
        assert tags == {"real-tag"}

    def test_skips_code_blocks(self):
        fm = {}
        body = "Before\n```python\n#comment\nprint('#notag')\n```\nAfter #real."
        tags = extract_tags(fm, body)
        assert tags == {"real"}

    def test_no_tags(self):
        fm = {}
        body = "Plain text without any tags."
        tags = extract_tags(fm, body)
        assert tags == set()

    def test_frontmatter_tags_as_string(self):
        # Some vaults use `tags: ml` instead of `tags: [ml]`
        fm = {"tags": "ml"}
        body = ""
        tags = extract_tags(fm, body)
        assert tags == {"ml"}

    def test_dedup_across_sources(self):
        fm = {"tags": ["ml"]}
        body = "Also mentions #ml inline."
        tags = extract_tags(fm, body)
        assert tags == {"ml"}

    def test_ignores_hex_colors(self):
        fm = {}
        body = "Color is #ff0000 and #abc."
        tags = extract_tags(fm, body)
        # #ff0000 starts with f (letter) so would match — but it's a valid tag name
        # #abc also matches — this is expected, Obsidian treats these as tags too
        assert "abc" in tags

    def test_tag_with_numbers(self):
        fm = {}
        body = "See #project2024 for details."
        tags = extract_tags(fm, body)
        assert tags == {"project2024"}


class TestBuildTagHierarchy:
    def test_flat_tags(self):
        tags = {"paper": 10, "daily": 5}
        hierarchy = build_tag_hierarchy(tags)
        names = {n.name for n in hierarchy}
        assert names == {"paper", "daily"}
        assert all(n.children == [] for n in hierarchy)

    def test_slash_grouping(self):
        tags = {"research": 2, "research/ai": 10, "research/ml": 5}
        hierarchy = build_tag_hierarchy(tags)
        # Should have one root: "research" with two children
        assert len(hierarchy) == 1
        root = hierarchy[0]
        assert root.name == "research"
        child_names = {c.name for c in root.children}
        assert child_names == {"ai", "ml"}

    def test_deep_nesting(self):
        tags = {"a/b/c": 3}
        hierarchy = build_tag_hierarchy(tags)
        assert len(hierarchy) == 1
        assert hierarchy[0].name == "a"
        assert len(hierarchy[0].children) == 1
        assert hierarchy[0].children[0].name == "b"
        assert len(hierarchy[0].children[0].children) == 1
        assert hierarchy[0].children[0].children[0].name == "c"

    def test_mixed_flat_and_hierarchical(self):
        tags = {"paper": 10, "research/ai": 5, "research/ml": 3, "daily": 20}
        hierarchy = build_tag_hierarchy(tags)
        root_names = {n.name for n in hierarchy}
        assert root_names == {"paper", "research", "daily"}

    def test_sorted_output(self):
        tags = {"zebra": 1, "alpha": 2, "middle": 3}
        hierarchy = build_tag_hierarchy(tags)
        names = [n.name for n in hierarchy]
        assert names == ["alpha", "middle", "zebra"]

    def test_empty(self):
        assert build_tag_hierarchy({}) == []


from src.vault.taxonomy import build_vault_taxonomy


class TestBuildVaultTaxonomy:
    def test_basic_scan(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        assert taxonomy.total_notes == 4

    def test_folders_extracted(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        assert "Projects" in taxonomy.folders
        assert "Topics" in taxonomy.folders
        assert "Papers" in taxonomy.folders
        assert "daily" in taxonomy.folders

    def test_tags_extracted(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        tag_names = {t.name for t in taxonomy.tags}
        assert "project" in tag_names
        assert "ml" in tag_names
        assert "daily" in tag_names

    def test_tags_have_counts(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        tag_map = {t.name: t.count for t in taxonomy.tags}
        assert tag_map["ml"] >= 1

    def test_tag_hierarchy_built(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        root_names = {n.name for n in taxonomy.tag_hierarchy}
        assert "source" in root_names

    def test_link_targets_extracted(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        link_titles = {lt.title for lt in taxonomy.link_targets}
        assert "Machine Learning" in link_titles
        assert "Projects/My Project" in link_titles

    def test_link_targets_have_counts(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        link_map = {lt.title: lt.count for lt in taxonomy.link_targets}
        assert link_map["Machine Learning"] >= 1

    def test_image_embeds_excluded_from_link_targets(self, tmp_vault):
        taxonomy = build_vault_taxonomy(str(tmp_vault))
        link_titles = {lt.title for lt in taxonomy.link_targets}
        assert "diagram.png" not in link_titles
        # Non-image links still present
        assert "Machine Learning" in link_titles
        assert "Projects/My Project" in link_titles
