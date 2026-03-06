import { useMemo, useState } from "react";
import { diffLines } from "diff";

interface Props {
  diff: string;
  filePath: string;
  isNew: boolean;
  originalContent?: string | null;
  proposedContent?: string;
}

interface DiffLine {
  type: "add" | "remove" | "context";
  content: string;
  oldNum: number | null;
  newNum: number | null;
}

/** Number of context lines to show before collapsing */
const COLLAPSE_THRESHOLD = 6;

function computeLines(
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

/** Group consecutive context lines for collapsing */
function groupLines(
  lines: DiffLine[]
): Array<
  { type: "lines"; lines: DiffLine[] } | { type: "collapsed"; lines: DiffLine[] }
> {
  const groups: Array<
    { type: "lines"; lines: DiffLine[] } | { type: "collapsed"; lines: DiffLine[] }
  > = [];
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

function CollapsedSection({ lines }: { lines: DiffLine[] }) {
  const [expanded, setExpanded] = useState(false);

  if (expanded) {
    return (
      <>
        {lines.map((line, i) => (
          <DiffRow key={`expanded-${i}`} line={line} />
        ))}
      </>
    );
  }

  return (
    <tr
      className="cursor-pointer hover:bg-elevated/50 transition-colors"
      onClick={() => setExpanded(true)}
    >
      <td
        colSpan={3}
        className="text-center text-xs text-muted py-1 px-3 select-none"
      >
        ··· {lines.length} unchanged lines ···
      </td>
    </tr>
  );
}

function DiffRow({ line }: { line: DiffLine }) {
  const bgClass =
    line.type === "add"
      ? "bg-green-bg"
      : line.type === "remove"
        ? "bg-red-bg"
        : "";
  const textClass =
    line.type === "add"
      ? "text-green"
      : line.type === "remove"
        ? "text-red"
        : "";
  const prefix =
    line.type === "add" ? "+" : line.type === "remove" ? "-" : " ";

  return (
    <tr className={bgClass}>
      <td className="w-[1px] whitespace-nowrap text-right pr-1 pl-2 text-[11px] text-muted/50 select-none align-top font-mono">
        {line.oldNum ?? ""}
      </td>
      <td className="w-[1px] whitespace-nowrap text-right pr-2 pl-1 text-[11px] text-muted/50 select-none align-top font-mono">
        {line.newNum ?? ""}
      </td>
      <td className={`pr-3 ${textClass}`}>
        <span className="inline-block w-4 text-center select-none opacity-60">
          {prefix}
        </span>
        {line.content}
      </td>
    </tr>
  );
}

export function DiffViewer({
  diff,
  filePath,
  isNew,
  originalContent,
  proposedContent,
}: Props) {
  const { lines, additions, deletions } = useMemo(
    () => computeLines(originalContent, proposedContent, diff, isNew),
    [originalContent, proposedContent, diff, isNew]
  );

  const groups = useMemo(() => groupLines(lines), [lines]);

  if (lines.length === 0) {
    return (
      <div className="border border-border rounded overflow-hidden mb-1">
        <div className="bg-elevated py-2 px-3 flex items-center gap-2 border-b border-border">
          <span
            className={`text-[11px] font-semibold py-0.5 px-1.5 rounded-[3px] uppercase ${isNew ? "bg-green-bg text-green" : "bg-yellow-bg text-yellow"}`}
          >
            {isNew ? "NEW FILE" : "MODIFY"}
          </span>
          <span className="font-mono text-[13px] text-muted">{filePath}</span>
        </div>
        <div className="p-4 text-muted text-center text-[13px]">
          No changes
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded overflow-hidden mb-1">
      <div className="bg-elevated py-2 px-3 flex items-center gap-2 border-b border-border">
        <span
          className={`text-[11px] font-semibold py-0.5 px-1.5 rounded-[3px] uppercase ${isNew ? "bg-green-bg text-green" : "bg-yellow-bg text-yellow"}`}
        >
          {isNew ? "NEW FILE" : "MODIFY"}
        </span>
        <span className="font-mono text-[13px] text-muted">{filePath}</span>
        <span className="ml-auto flex gap-2 text-xs font-mono">
          {additions > 0 && <span className="text-green">+{additions}</span>}
          {deletions > 0 && <span className="text-red">-{deletions}</span>}
        </span>
      </div>
      <div className="overflow-x-auto bg-bg">
        <table className="w-full font-mono text-xs leading-relaxed border-collapse">
          <tbody>
            {groups.map((group, gi) => {
              if (group.type === "collapsed") {
                return (
                  <CollapsedSection key={`c-${gi}`} lines={group.lines} />
                );
              }
              return group.lines.map((line, li) => (
                <DiffRow key={`${gi}-${li}`} line={line} />
              ));
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
