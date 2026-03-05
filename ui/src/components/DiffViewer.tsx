interface Props {
  diff: string;
  filePath: string;
  isNew: boolean;
}

export function DiffViewer({ diff, filePath, isNew }: Props) {
  if (!diff) {
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

  const lines = diff.split("\n");

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
      <pre className="py-2 font-mono text-xs leading-relaxed overflow-x-auto m-0 bg-bg">
        {lines.map((line, i) => {
          let cls = "py-0 px-3 min-h-[20px]";
          if (line.startsWith("+") && !line.startsWith("+++")) {
            cls += " bg-green-bg text-green";
          } else if (line.startsWith("-") && !line.startsWith("---")) {
            cls += " bg-red-bg text-red";
          } else if (line.startsWith("@@")) {
            cls += " text-accent";
          }
          return (
            <div key={i} className={cls}>
              {line}
            </div>
          );
        })}
      </pre>
    </div>
  );
}
