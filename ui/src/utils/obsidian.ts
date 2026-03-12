/**
 * Obsidian-specific markdown preprocessing utilities.
 * Transforms Obsidian syntax into HTML spans that rehype-raw can render.
 */

/** Transform Obsidian syntax into renderable HTML spans */
export function preprocessObsidian(content: string): string {
  let result = content;

  // Embeds: ![[Note]] or ![[Note|display]]
  result = result.replace(
    /!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
    (_match, note: string, display?: string) =>
      `<span class="embed-link">${display ?? note}</span>`,
  );

  // Wikilinks: [[Note]] or [[Note|display]] or [[Note#Heading]]
  result = result.replace(
    /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
    (_match, note: string, display?: string) =>
      `<span class="wikilink">${display ?? note}</span>`,
  );

  // Tags: #tag or #nested/tag (but not headings — must be preceded by whitespace or start of line)
  result = result.replace(
    /(^|[\s(])#([\w][\w/-]*)/gm,
    (_match, prefix: string, tag: string) =>
      `${prefix}<span class="obsidian-tag">#${tag}</span>`,
  );

  return result;
}

/** Parse YAML frontmatter block from markdown content */
export function extractFrontmatter(content: string): {
  frontmatter: Record<string, unknown> | null;
  body: string;
} {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
  if (!match) return { frontmatter: null, body: content };

  const yamlBlock = match[1];
  const body = content.slice(match[0].length);

  // Simple YAML key-value parser (handles strings, arrays, numbers, booleans)
  const frontmatter: Record<string, unknown> = {};
  const lines = yamlBlock.split("\n");

  let currentKey: string | null = null;
  let currentArray: string[] | null = null;

  for (const line of lines) {
    // Array item continuation: "  - value"
    const arrayItemMatch = line.match(/^\s+-\s+(.+)/);
    if (arrayItemMatch && currentKey && currentArray) {
      currentArray.push(arrayItemMatch[1].replace(/^["']|["']$/g, ""));
      frontmatter[currentKey] = currentArray;
      continue;
    }

    // Inline array: key: [val1, val2]
    const inlineArrayMatch = line.match(/^(\w[\w\s]*?):\s*\[([^\]]*)\]/);
    if (inlineArrayMatch) {
      currentKey = inlineArrayMatch[1].trim();
      currentArray = null;
      const items = inlineArrayMatch[2]
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean);
      frontmatter[currentKey] = items;
      continue;
    }

    // Key-value pair: key: value
    const kvMatch = line.match(/^(\w[\w\s]*?):\s*(.*)/);
    if (kvMatch) {
      currentKey = kvMatch[1].trim();
      const value = kvMatch[2].trim().replace(/^["']|["']$/g, "");
      if (value === "") {
        // Could be start of a block array
        currentArray = [];
        frontmatter[currentKey] = "";
      } else {
        currentArray = null;
        frontmatter[currentKey] = value;
      }
    }
  }

  return { frontmatter, body };
}
