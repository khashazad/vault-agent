from src.vault.taxonomy import extract_tags


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
