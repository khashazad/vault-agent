import { useState, useMemo } from "react";
import type { ZoteroCollection } from "../types";

const FOLDER_ICON_PATH =
  "M1 3.5A1.5 1.5 0 0 1 2.5 2h3.879a1.5 1.5 0 0 1 1.06.44l1.122 1.12A1.5 1.5 0 0 0 9.62 4H13.5A1.5 1.5 0 0 1 15 5.5v7a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 12.5v-9z";

function FolderIcon({ size = 13 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="currentColor"
      className="flex-shrink-0 opacity-60"
    >
      <path d={FOLDER_ICON_PATH} />
    </svg>
  );
}

function itemClassName(isActive: boolean) {
  return `flex items-center gap-1.5 py-1.5 rounded text-left cursor-pointer border-none w-full transition-colors ${
    isActive
      ? "bg-accent/15 text-accent font-medium"
      : "bg-transparent text-foreground hover:bg-surface"
  }`;
}

interface TreeNode {
  collection: ZoteroCollection;
  children: TreeNode[];
}

function buildTree(collections: ZoteroCollection[]): TreeNode[] {
  const byKey = new Map<string, TreeNode>();
  for (const c of collections) {
    byKey.set(c.key, { collection: c, children: [] });
  }
  const roots: TreeNode[] = [];
  for (const node of byKey.values()) {
    const parentKey = node.collection.parent_collection;
    if (parentKey && byKey.has(parentKey)) {
      byKey.get(parentKey)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  // Sort children alphabetically
  const sortChildren = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.collection.name.localeCompare(b.collection.name));
    for (const n of nodes) sortChildren(n.children);
  };
  sortChildren(roots);
  return roots;
}

interface Props {
  collections: ZoteroCollection[];
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
}

export function CollectionTree({ collections, selectedKey, onSelect }: Props) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const tree = useMemo(() => buildTree(collections), [collections]);

  function toggleExpand(
    key: string,
    e?: React.MouseEvent | React.KeyboardEvent,
  ) {
    e?.stopPropagation();
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-0.5 text-sm">
      {/* My Library (root) */}
      <button
        onClick={() => onSelect(null)}
        className={`${itemClassName(selectedKey === null)} gap-2 px-2`}
      >
        <FolderIcon size={14} />
        <span className="truncate">My Library</span>
      </button>

      {/* Collection tree */}
      {tree.map((node) => (
        <TreeNodeItem
          key={node.collection.key}
          node={node}
          depth={1}
          selectedKey={selectedKey}
          expandedKeys={expandedKeys}
          onSelect={onSelect}
          onToggle={toggleExpand}
        />
      ))}
    </div>
  );
}

export function CollectionTreeSkeleton() {
  const widths = [100, 75, 88, 65, 80];
  return (
    <div className="flex flex-col gap-2.5 animate-pulse py-1">
      <div className="h-5 bg-surface rounded w-24" />
      {widths.map((w, i) => (
        <div
          key={i}
          className="h-4 bg-surface rounded"
          style={{ width: `${w}%`, marginLeft: i > 0 ? "16px" : 0 }}
        />
      ))}
    </div>
  );
}

interface TreeNodeItemProps {
  node: TreeNode;
  depth: number;
  selectedKey: string | null;
  expandedKeys: Set<string>;
  onSelect: (key: string | null) => void;
  onToggle: (key: string, e?: React.MouseEvent | React.KeyboardEvent) => void;
}

function TreeNodeItem({
  node,
  depth,
  selectedKey,
  expandedKeys,
  onSelect,
  onToggle,
}: TreeNodeItemProps) {
  const { collection, children } = node;
  const isSelected = selectedKey === collection.key;
  const isExpanded = expandedKeys.has(collection.key);
  const hasChildren = children.length > 0;

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        onClick={() => onSelect(collection.key)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(collection.key);
          }
        }}
        className={itemClassName(isSelected)}
        style={{ paddingLeft: `${depth * 16 + 8}px`, paddingRight: "8px" }}
      >
        {/* Expand/collapse chevron */}
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggle(collection.key, e);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                e.stopPropagation();
                onToggle(collection.key, e);
              }
            }}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? "Collapse" : "Expand"}
            className="flex items-center justify-center w-4 h-4 flex-shrink-0 text-muted hover:text-foreground bg-transparent border-none cursor-pointer p-0"
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="currentColor"
              className={`transition-transform ${isExpanded ? "rotate-90" : ""}`}
            >
              <path d="M3 1l5 4-5 4V1z" />
            </svg>
          </button>
        ) : (
          <span className="w-4 flex-shrink-0" />
        )}

        <FolderIcon />

        <span className="truncate" title={collection.name}>
          {collection.name}
        </span>

        {/* Item count — only for leaf collections */}
        {!hasChildren && (
          <span className="ml-auto text-[10px] text-muted flex-shrink-0">
            {collection.num_items}
          </span>
        )}
      </div>

      {/* Recursive children */}
      {isExpanded &&
        children.map((child) => (
          <TreeNodeItem
            key={child.collection.key}
            node={child}
            depth={depth + 1}
            selectedKey={selectedKey}
            expandedKeys={expandedKeys}
            onSelect={onSelect}
            onToggle={onToggle}
          />
        ))}
    </>
  );
}
