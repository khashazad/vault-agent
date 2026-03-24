import { describe, it, expect } from "vitest";
import {
  preprocessObsidian,
  extractFrontmatter,
  normalizeLatexDelimiters,
} from "../../utils/obsidian";

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
    expect(result).toContain(
      '<span class="obsidian-tag">#ml/deep-learning</span>',
    );
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

  it("converts image embeds to img tags", () => {
    const result = preprocessObsidian("![[photo.png]]");
    expect(result).toContain(
      '<img src="/vault/assets/photo.png" alt="photo.png" class="obsidian-embed-image" />',
    );
  });

  it("converts image embeds with various extensions", () => {
    for (const ext of ["jpg", "jpeg", "gif", "svg", "webp", "bmp", "avif"]) {
      const result = preprocessObsidian(`![[image.${ext}]]`);
      expect(result).toContain(`src="/vault/assets/image.${ext}"`);
      expect(result).toContain('class="obsidian-embed-image"');
    }
  });

  it("uses display text as alt for image embeds", () => {
    const result = preprocessObsidian("![[photo.png|My Photo]]");
    expect(result).toContain('alt="My Photo"');
    expect(result).toContain('src="/vault/assets/photo.png"');
  });

  it("keeps non-image embeds as spans", () => {
    const result = preprocessObsidian("![[Some Note]]");
    expect(result).toContain('<span class="embed-link">Some Note</span>');
    expect(result).not.toContain("<img");
  });

  it("encodes spaces in image embed paths", () => {
    const result = preprocessObsidian("![[my folder/photo image.png]]");
    expect(result).toContain(
      'src="/vault/assets/my%20folder/photo%20image.png"',
    );
  });
});

describe("normalizeLatexDelimiters", () => {
  it("converts inline \\(...\\) to $...$", () => {
    expect(normalizeLatexDelimiters("The value \\(\\gamma\\) is key")).toBe(
      "The value $\\gamma$ is key",
    );
  });

  it("converts display \\[...\\] to $$...$$", () => {
    expect(normalizeLatexDelimiters("\\[E = mc^2\\]")).toBe("$$E = mc^2$$");
  });

  it("handles multiline display math", () => {
    const input = "\\[\nFL(p_t) = -\\alpha_t\n\\]";
    expect(normalizeLatexDelimiters(input)).toBe(
      "$$\nFL(p_t) = -\\alpha_t\n$$",
    );
  });

  it("leaves $...$ and $$...$$ unchanged", () => {
    const input = "Inline $x^2$ and display $$y^2$$";
    expect(normalizeLatexDelimiters(input)).toBe(input);
  });

  it("handles multiple inline expressions", () => {
    const input = "Both \\(\\alpha\\) and \\(\\beta\\) matter";
    expect(normalizeLatexDelimiters(input)).toBe(
      "Both $\\alpha$ and $\\beta$ matter",
    );
  });
});

describe("extractFrontmatter", () => {
  it("parses valid YAML frontmatter", () => {
    const content =
      "---\ntags: [ml, paper]\ncreated: 2024-01-01\n---\n\n# Body";
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
