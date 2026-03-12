import { describe, it, expect } from "vitest";
import { preprocessObsidian, extractFrontmatter } from "../../utils/obsidian";

describe("preprocessObsidian", () => {
  it("converts wikilinks to spans", () => {
    const result = preprocessObsidian("See [[My Note]] for details.");
    expect(result).toContain('<span class="wikilink">My Note</span>');
  });

  it("handles wikilinks with display text", () => {
    const result = preprocessObsidian("[[Real Title|display text]]");
    expect(result).toContain('<span class="wikilink">display text</span>');
  });

  it("converts embeds to embed-link spans", () => {
    const result = preprocessObsidian("![[Embedded Note]]");
    expect(result).toContain('<span class="embed-link">Embedded Note</span>');
  });

  it("converts embed with display text", () => {
    const result = preprocessObsidian("![[Note|Custom Display]]");
    expect(result).toContain('<span class="embed-link">Custom Display</span>');
  });

  it("converts inline tags", () => {
    const result = preprocessObsidian("Tagged #project and #ml/deep-learning.");
    expect(result).toContain('<span class="obsidian-tag">#project</span>');
    expect(result).toContain('<span class="obsidian-tag">#ml/deep-learning</span>');
  });

  it("does not convert headings as tags", () => {
    const result = preprocessObsidian("## Heading");
    expect(result).not.toContain("obsidian-tag");
    expect(result).toBe("## Heading");
  });

  it("handles text with no special syntax", () => {
    const plain = "Just plain text.";
    expect(preprocessObsidian(plain)).toBe(plain);
  });

  it("handles multiple wikilinks in one line", () => {
    const result = preprocessObsidian("Links to [[A]] and [[B]].");
    expect(result).toContain('<span class="wikilink">A</span>');
    expect(result).toContain('<span class="wikilink">B</span>');
  });
});

describe("extractFrontmatter", () => {
  it("parses valid YAML frontmatter", () => {
    const content = "---\ntags: [ml, paper]\ncreated: 2024-01-01\n---\n\n# Body";
    const { frontmatter, body } = extractFrontmatter(content);
    expect(frontmatter).not.toBeNull();
    expect(frontmatter!.tags).toEqual(["ml", "paper"]);
    expect(body.trim()).toBe("# Body");
  });

  it("handles inline arrays", () => {
    const content = "---\ntags: [a, b, c]\n---\n\nBody";
    const { frontmatter } = extractFrontmatter(content);
    expect(frontmatter!.tags).toEqual(["a", "b", "c"]);
  });

  it("handles block arrays", () => {
    const content = "---\naliases:\n  - Alias One\n  - Alias Two\n---\n\nBody";
    const { frontmatter } = extractFrontmatter(content);
    expect(frontmatter!.aliases).toEqual(["Alias One", "Alias Two"]);
  });

  it("returns null frontmatter for no delimiter", () => {
    const content = "# No frontmatter\n\nJust content.";
    const { frontmatter, body } = extractFrontmatter(content);
    expect(frontmatter).toBeNull();
    expect(body).toBe(content);
  });

  it("returns null for empty frontmatter (no content between delimiters)", () => {
    const content = "---\n---\n\nBody";
    const { frontmatter, body } = extractFrontmatter(content);
    // Regex requires \n before closing --- so empty block doesn't match
    expect(frontmatter).toBeNull();
    expect(body).toBe(content);
  });
});
