import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { ProposedChange } from "../types";

interface Props {
  changes: ProposedChange[];
  selectedId: string | null;
  onSelect: (changeId: string) => void;
}

interface FileNode {
  kind: "file";
  name: string;
  path: string;
  change: ProposedChange;
}

interface FolderNode {
  kind: "folder";
  name: string;
  path: string;
  children: Map<string, TreeNode>;
}

type TreeNode = FileNode | FolderNode;

function makeFolder(name: string, path: string): FolderNode {
  return {
    kind: "folder",
    name,
    path,
    children: new Map(),
  };
}

function buildTree(changes: ProposedChange[]) {
  const root = makeFolder("", "");

  for (const change of changes) {
    const rawPath = String(change.input.path ?? "");
    const parts = rawPath.split("/").filter(Boolean);
    let current = root;

    parts.forEach((part, index) => {
      const nodePath = parts.slice(0, index + 1).join("/");
      const isFile = index === parts.length - 1;

      if (isFile) {
        current.children.set(part, {
          kind: "file",
          name: part,
          path: nodePath,
          change,
        });
        return;
      }

      const existing = current.children.get(part);
      if (existing?.kind === "folder") {
        current = existing;
        return;
      }

      const folder = makeFolder(part, nodePath);
      current.children.set(part, folder);
      current = folder;
    });
  }

  return root;
}

function sortNodes(nodes: TreeNode[]) {
  return [...nodes].sort((left, right) => {
    if (left.kind !== right.kind) {
      return left.kind === "folder" ? -1 : 1;
    }
    return left.name.localeCompare(right.name);
  });
}

function badgeClasses(toolName: string) {
  if (toolName === "create_note") {
    return "bg-green/15 text-green";
  }
  if (toolName === "delete_note") {
    return "bg-red/15 text-red";
  }
  return "bg-yellow/15 text-yellow";
}

function badgeLabel(toolName: string) {
  if (toolName === "create_note") {
    return "NEW";
  }
  if (toolName === "delete_note") {
    return "DEL";
  }
  return "MOD";
}

export function FileExplorer({ changes, selectedId, onSelect }: Props) {
  const tree = useMemo(() => buildTree(changes), [changes]);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const pendingCount = changes.filter(
    (change) => change.status === "pending",
  ).length;
  const reviewedCount = changes.length - pendingCount;

  function toggleFolder(path: string) {
    setCollapsed((prev) => ({ ...prev, [path]: !prev[path] }));
  }

  function renderNodes(nodes: TreeNode[], depth = 0): ReactNode[] {
    return sortNodes(nodes).flatMap((node) => {
      if (node.kind === "folder") {
        const isCollapsed = collapsed[node.path] ?? false;
        const icon = isCollapsed ? "\u25b6" : "\u25be";

        return [
          <button
            key={node.path}
            type="button"
            onClick={() => toggleFolder(node.path)}
            className="flex items-center gap-2 w-full border-none bg-transparent text-left px-3 py-1.5 text-sm text-muted hover:text-foreground cursor-pointer"
            style={{ paddingLeft: `${depth * 14 + 12}px` }}
          >
            <span className="text-[10px] text-muted/70">{icon}</span>
            <span>{node.name}</span>
          </button>,
          ...(!isCollapsed
            ? renderNodes([...node.children.values()], depth + 1)
            : []),
        ];
      }

      const isSelected = selectedId === node.change.id;
      const isReviewed = node.change.status !== "pending";
      const reviewIcon =
        node.change.status === "approved"
          ? "\u2713"
          : node.change.status === "rejected"
            ? "\u2717"
            : null;
      const reviewClass =
        node.change.status === "approved" ? "text-green" : "text-red";

      return [
        <button
          key={node.path}
          type="button"
          data-testid={`file-row-${node.change.id}`}
          onClick={() => onSelect(node.change.id)}
          className={`flex items-center gap-2 w-full rounded-md border px-3 py-2 text-left cursor-pointer transition-colors ${
            isSelected
              ? "border-accent bg-accent/10"
              : "border-transparent hover:border-border hover:bg-elevated/60"
          }`}
          style={{ paddingLeft: `${depth * 14 + 12}px` }}
        >
          <span className="text-muted/70">#</span>
          <span
            className={`min-w-0 flex-1 truncate text-sm font-mono ${
              isReviewed ? "text-muted" : "text-foreground"
            }`}
          >
            {node.name}
          </span>
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${badgeClasses(node.change.tool_name)}`}
          >
            {badgeLabel(node.change.tool_name)}
          </span>
          {reviewIcon && (
            <span
              aria-hidden="true"
              className={`text-xs opacity-70 ${reviewClass}`}
            >
              {reviewIcon}
            </span>
          )}
        </button>,
      ];
    });
  }

  return (
    <aside className="w-[250px] min-w-[250px] border border-border rounded-xl bg-surface overflow-hidden">
      <div className="border-b border-border px-4 py-3">
        <div className="text-xs uppercase tracking-[0.16em] text-muted">
          Files
        </div>
        <div className="mt-1 text-sm text-foreground">
          {pendingCount} to review / {reviewedCount} reviewed
        </div>
      </div>
      <div className="flex flex-col gap-0.5 p-2 overflow-y-auto max-h-[520px]">
        {renderNodes([...tree.children.values()])}
      </div>
    </aside>
  );
}
