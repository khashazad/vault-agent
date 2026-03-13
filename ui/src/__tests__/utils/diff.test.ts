import { describe, it, expect } from "vitest";
import { computeLines, groupLines, COLLAPSE_THRESHOLD } from "../../utils/diff";
import type { DiffLine } from "../../utils/diff";

describe("computeLines", () => {
  it("returns all additions for new file", () => {
    const { lines, additions, deletions } = computeLines(
      null,
      "# Title\n\nContent.",
      "",
      true,
    );
    expect(lines.every((l) => l.type === "add")).toBe(true);
    expect(additions).toBe(3); // 3 lines
    expect(deletions).toBe(0);
  });

  it("computes structured diff for modified content", () => {
    const original = "Line 1\nLine 2\nLine 3\n";
    const proposed = "Line 1\nModified 2\nLine 3\nLine 4\n";
    const { lines, additions, deletions } = computeLines(
      original,
      proposed,
      "",
      false,
    );
    expect(additions).toBeGreaterThan(0);
    expect(deletions).toBeGreaterThan(0);
    expect(lines.some((l) => l.type === "add")).toBe(true);
    expect(lines.some((l) => l.type === "remove")).toBe(true);
    expect(lines.some((l) => l.type === "context")).toBe(true);
  });

  it("falls back to unified diff parsing", () => {
    const diff =
      "--- a/note.md\n+++ b/note.md\n@@ -1,2 +1,2 @@\n-old line\n+new line\n context\n";
    const { lines, additions, deletions } = computeLines(
      undefined,
      undefined,
      diff,
      false,
    );
    expect(additions).toBe(1);
    expect(deletions).toBe(1);
    expect(lines.find((l) => l.type === "add")?.content).toBe("new line");
    expect(lines.find((l) => l.type === "remove")?.content).toBe("old line");
  });

  it("returns empty for no content and no diff", () => {
    const { lines } = computeLines(undefined, undefined, "", false);
    expect(lines).toEqual([]);
  });

  it("assigns line numbers correctly", () => {
    const { lines } = computeLines(null, "A\nB\nC", "", true);
    expect(lines[0].newNum).toBe(1);
    expect(lines[1].newNum).toBe(2);
    expect(lines[2].newNum).toBe(3);
    // oldNum should be null for additions
    expect(lines.every((l) => l.oldNum === null)).toBe(true);
  });
});

describe("groupLines", () => {
  function makeLine(type: DiffLine["type"], i: number): DiffLine {
    return { type, content: `line ${i}`, oldNum: i, newNum: i };
  }

  it("collapses long context sections", () => {
    // 10 context lines should get collapsed
    const lines: DiffLine[] = [
      makeLine("add", 0),
      ...Array.from({ length: 10 }, (_, i) => makeLine("context", i + 1)),
      makeLine("add", 11),
    ];
    const groups = groupLines(lines);
    const collapsed = groups.filter((g) => g.type === "collapsed");
    expect(collapsed.length).toBe(1);
    // Middle should be collapsed (10 - 3 head - 3 tail = 4)
    expect(collapsed[0].lines.length).toBe(4);
  });

  it("does not collapse short context", () => {
    const lines: DiffLine[] = [
      makeLine("add", 0),
      makeLine("context", 1),
      makeLine("context", 2),
      makeLine("add", 3),
    ];
    const groups = groupLines(lines);
    const collapsed = groups.filter((g) => g.type === "collapsed");
    expect(collapsed.length).toBe(0);
  });

  it("keeps add/remove lines in 'lines' groups", () => {
    const lines: DiffLine[] = [makeLine("remove", 1), makeLine("add", 1)];
    const groups = groupLines(lines);
    expect(groups.length).toBe(1);
    expect(groups[0].type).toBe("lines");
    expect(groups[0].lines.length).toBe(2);
  });

  it("handles empty input", () => {
    expect(groupLines([])).toEqual([]);
  });

  it("preserves head and tail context around collapsed section", () => {
    const lines: DiffLine[] = Array.from({ length: 12 }, (_, i) =>
      makeLine("context", i),
    );
    const groups = groupLines(lines);
    // Should be: head(3) + collapsed(6) + tail(3)
    expect(groups.length).toBe(3);
    expect(groups[0].type).toBe("lines");
    expect(groups[0].lines.length).toBe(3);
    expect(groups[1].type).toBe("collapsed");
    expect(groups[2].type).toBe("lines");
    expect(groups[2].lines.length).toBe(3);
  });
});
