import { diffLines } from "diff";

export interface DiffLine {
  type: "add" | "remove" | "context";
  content: string;
  oldNum: number | null;
  newNum: number | null;
}

/** Number of context lines to show before collapsing */
export const COLLAPSE_THRESHOLD = 6;

export function computeLines(
  originalContent: string | null | undefined,
  proposedContent: string | undefined,
  fallbackDiff: string,
  isNew: boolean
): { lines: DiffLine[]; additions: number; deletions: number } {
  // If we have structured content, use diffLines
  if (proposedContent !== undefined) {
    const original = originalContent ?? "";
    const proposed = proposedContent;

    if (isNew || !original) {
      // New file — all additions
      const fileLines = proposed.split("\n");
      return {
        lines: fileLines.map((content, i) => ({
          type: "add" as const,
          content,
          oldNum: null,
          newNum: i + 1,
        })),
        additions: fileLines.length,
        deletions: 0,
      };
    }

    const changes = diffLines(original, proposed);
    const lines: DiffLine[] = [];
    let oldNum = 1;
    let newNum = 1;
    let additions = 0;
    let deletions = 0;

    for (const change of changes) {
      const changeLines = change.value.replace(/\n$/, "").split("\n");
      for (const line of changeLines) {
        if (change.added) {
          lines.push({ type: "add", content: line, oldNum: null, newNum });
          newNum++;
          additions++;
        } else if (change.removed) {
          lines.push({ type: "remove", content: line, oldNum, newNum: null });
          oldNum++;
          deletions++;
        } else {
          lines.push({ type: "context", content: line, oldNum, newNum });
          oldNum++;
          newNum++;
        }
      }
    }

    return { lines, additions, deletions };
  }

  // Fallback: parse unified diff text
  if (!fallbackDiff) return { lines: [], additions: 0, deletions: 0 };

  const rawLines = fallbackDiff.split("\n");
  const lines: DiffLine[] = [];
  let oldNum = 1;
  let newNum = 1;
  let additions = 0;
  let deletions = 0;

  for (const raw of rawLines) {
    if (raw.startsWith("@@")) {
      const match = raw.match(/@@ -(\d+)/);
      if (match) {
        oldNum = parseInt(match[1], 10);
        newNum = oldNum;
      }
      continue;
    }
    if (raw.startsWith("---") || raw.startsWith("+++")) continue;

    if (raw.startsWith("+")) {
      lines.push({
        type: "add",
        content: raw.slice(1),
        oldNum: null,
        newNum,
      });
      newNum++;
      additions++;
    } else if (raw.startsWith("-")) {
      lines.push({
        type: "remove",
        content: raw.slice(1),
        oldNum,
        newNum: null,
      });
      oldNum++;
      deletions++;
    } else {
      lines.push({
        type: "context",
        content: raw.startsWith(" ") ? raw.slice(1) : raw,
        oldNum,
        newNum,
      });
      oldNum++;
      newNum++;
    }
  }

  return { lines, additions, deletions };
}

export type LineGroup =
  | { type: "lines"; lines: DiffLine[] }
  | { type: "collapsed"; lines: DiffLine[] };

/** Group consecutive context lines for collapsing */
export function groupLines(lines: DiffLine[]): LineGroup[] {
  const groups: LineGroup[] = [];
  let contextBuffer: DiffLine[] = [];

  const flushContext = () => {
    if (contextBuffer.length === 0) return;
    if (contextBuffer.length > COLLAPSE_THRESHOLD) {
      // Show first 3, collapse middle, show last 3
      const head = contextBuffer.slice(0, 3);
      const middle = contextBuffer.slice(3, -3);
      const tail = contextBuffer.slice(-3);
      if (head.length > 0) groups.push({ type: "lines", lines: head });
      if (middle.length > 0) groups.push({ type: "collapsed", lines: middle });
      if (tail.length > 0) groups.push({ type: "lines", lines: tail });
    } else {
      groups.push({ type: "lines", lines: contextBuffer });
    }
    contextBuffer = [];
  };

  for (const line of lines) {
    if (line.type === "context") {
      contextBuffer.push(line);
    } else {
      flushContext();
      const last = groups[groups.length - 1];
      if (last && last.type === "lines") {
        last.lines.push(line);
      } else {
        groups.push({ type: "lines", lines: [line] });
      }
    }
  }
  flushContext();

  return groups;
}
