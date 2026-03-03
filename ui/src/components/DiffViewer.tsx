interface Props {
  diff: string;
  filePath: string;
  isNew: boolean;
}

export function DiffViewer({ diff, filePath, isNew }: Props) {
  if (!diff) {
    return (
      <div className="diff-viewer">
        <div className="diff-header">
          <span className={`diff-badge ${isNew ? "new" : "modify"}`}>
            {isNew ? "NEW FILE" : "MODIFY"}
          </span>
          <span className="diff-path">{filePath}</span>
        </div>
        <div className="diff-empty">No changes</div>
      </div>
    );
  }

  const lines = diff.split("\n");

  return (
    <div className="diff-viewer">
      <div className="diff-header">
        <span className={`diff-badge ${isNew ? "new" : "modify"}`}>
          {isNew ? "NEW FILE" : "MODIFY"}
        </span>
        <span className="diff-path">{filePath}</span>
      </div>
      <pre className="diff-content">
        {lines.map((line, i) => {
          let cls = "diff-line";
          if (line.startsWith("+") && !line.startsWith("+++")) {
            cls += " added";
          } else if (line.startsWith("-") && !line.startsWith("---")) {
            cls += " removed";
          } else if (line.startsWith("@@")) {
            cls += " hunk";
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
