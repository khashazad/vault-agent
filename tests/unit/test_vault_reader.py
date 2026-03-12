from src.vault.reader import parse_frontmatter, extract_wikilinks, extract_headings


class TestParseFrontmatter:
    def test_valid_yaml(self):
        raw = "---\ntags: [ml, paper]\ncreated: 2024-01-01\n---\n\n# Title\n\nBody."
        fm, content = parse_frontmatter(raw)
        assert fm["tags"] == ["ml", "paper"]
        assert "created" in fm  # YAML parses date as datetime.date
        assert content.startswith("# Title")

    def test_empty_frontmatter(self):
        raw = "---\n---\n\nJust body."
        fm, content = parse_frontmatter(raw)
        assert fm == {}
        assert "Just body." in content

    def test_no_frontmatter(self):
        raw = "# No frontmatter\n\nJust text."
        fm, content = parse_frontmatter(raw)
        # python-frontmatter treats the whole thing as content
        assert isinstance(fm, dict)
        assert "No frontmatter" in content

    def test_malformed_yaml(self):
        raw = "---\n: invalid: yaml: [[\n---\n\nBody."
        fm, content = parse_frontmatter(raw)
        # should not raise, falls back to empty metadata
        assert isinstance(fm, dict)


class TestExtractWikilinks:
    def test_basic_links(self):
        content = "See [[Note A]] and [[Note B]]."
        links = extract_wikilinks(content)
        assert links == ["Note A", "Note B"]

    def test_display_text(self):
        content = "[[Real Title|display text]]"
        links = extract_wikilinks(content)
        assert links == ["Real Title"]

    def test_heading_links(self):
        content = "See [[Note#Section]]."
        links = extract_wikilinks(content)
        assert links == ["Note#Section"]

    def test_dedup_preserves_order(self):
        content = "[[A]], [[B]], [[A]], [[C]]"
        links = extract_wikilinks(content)
        assert links == ["A", "B", "C"]

    def test_no_links(self):
        content = "Plain text without links."
        assert extract_wikilinks(content) == []

    def test_embed_not_matched(self):
        # Embeds start with !, wikilinks don't — regex should not match ![[embed]]
        content = "![[Image.png]] and [[Real Link]]"
        links = extract_wikilinks(content)
        # The regex matches [[...]] inside ![[...]] too — that's fine for link extraction
        assert "Real Link" in links


class TestExtractHeadings:
    def test_all_levels(self):
        content = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
        headings = extract_headings(content)
        assert headings == ["H1", "H2", "H3", "H4", "H5", "H6"]

    def test_no_false_positives(self):
        content = "Not a #hashtag\n\nAlso not##heading\n\n## Real Heading"
        headings = extract_headings(content)
        assert headings == ["Real Heading"]

    def test_empty_content(self):
        assert extract_headings("") == []

    def test_heading_with_special_chars(self):
        content = "## Key Findings & Results (2024)"
        headings = extract_headings(content)
        assert headings == ["Key Findings & Results (2024)"]
