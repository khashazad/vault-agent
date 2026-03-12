import { useMemo, useState } from "react";
import { computeLines, groupLines } from "../utils/diff";
import type { DiffLine } from "../utils/diff";

interface Props {
  diff: string;
  filePath: string;
  isNew: boolean;
  originalContent?: string | null;
  proposedContent?: string;
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
