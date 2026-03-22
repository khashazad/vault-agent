import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router";
import { ErrorAlert } from "../components/ErrorAlert";
import { fetchVaultTaxonomy, applyTaxonomyCuration } from "../api/client";
import type {
  VaultTaxonomy,
  TagNode,
  TaxonomyCurationOp,
  TaxonomyCurationOpType,
} from "../types";

type Tab = "folders" | "tags" | "links";

type ModalOp =
  | "rename_tag"
  | "merge_tags"
  | "delete_tag"
  | "rename_folder"
  | "rename_link"
  | "merge_links";

const TAB_LABELS: Record<Tab, string> = {
  folders: "Folders",
  tags: "Tags",
  links: "Link Targets",
};

const OP_LABELS: Record<ModalOp, string> = {
  rename_tag: "Rename Tag",
  merge_tags: "Merge Tags",
  delete_tag: "Delete Tag",
  rename_folder: "Rename Folder",
  rename_link: "Rename Link",
  merge_links: "Merge Links",
};

function needsValue(op: ModalOp): boolean {
  return op !== "delete_tag";
}

// Folder icon SVG
function FolderIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="text-accent flex-shrink-0"
    >
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  );
}

// Recursive tag tree node
function TagTreeNode({
  node,
  depth,
  expanded,
  onToggle,
  filter,
  onContextMenu,
  highlightedTag,
}: {
  node: TagNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (name: string) => void;
  filter: string;
  onContextMenu: (e: React.MouseEvent, name: string) => void;
  highlightedTag: string | null;
}) {
  const hasChildren = node.children.length > 0;
  const isExpanded = expanded.has(node.name);
  const lowerFilter = filter.toLowerCase();

  // Filter: show node if it matches or any descendant matches
  const matchesSelf = node.name.toLowerCase().includes(lowerFilter);
  const matchesDescendant =
    !matchesSelf && hasChildren && nodeMatchesFilter(node, lowerFilter);
  if (lowerFilter && !matchesSelf && !matchesDescendant) return null;

  const isHighlighted = highlightedTag === node.name;

  return (
    <>
      <div
        className={`flex items-center gap-1.5 py-1 px-2 rounded transition-colors cursor-default ${
          isHighlighted
            ? "bg-orange/10 ring-1 ring-orange/40"
            : "hover:bg-elevated/50"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onContextMenu={(e) => onContextMenu(e, node.name)}
      >
        {hasChildren ? (
          <button
            onClick={() => onToggle(node.name)}
            className="text-muted hover:text-text bg-transparent border-none cursor-pointer p-0 text-xs leading-none"
          >
            {isExpanded ? "\u25BC" : "\u25B6"}
          </button>
        ) : (
          <span className="w-3" />
        )}
        <span className="text-xs font-mono text-text">{node.name}</span>
        {node.description && (
          <span
            className="text-[10px] text-muted ml-auto truncate max-w-[120px]"
            title={node.description}
          >
            {node.description}
          </span>
        )}
      </div>
      {hasChildren &&
        (isExpanded || (lowerFilter && matchesDescendant)) &&
        node.children.map((child) => (
          <TagTreeNode
            key={child.name}
            node={child}
            depth={depth + 1}
            expanded={expanded}
            onToggle={onToggle}
            filter={filter}
            onContextMenu={onContextMenu}
            highlightedTag={highlightedTag}
          />
        ))}
    </>
  );
}

function nodeMatchesFilter(node: TagNode, filter: string): boolean {
  if (node.name.toLowerCase().includes(filter)) return true;
  return node.children.some((c) => nodeMatchesFilter(c, filter));
}

// Refresh icon
function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={spinning ? "animate-spin" : ""}
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
      <polyline points="21 3 21 9 15 9" />
    </svg>
  );
}

export function TaxonomyPage() {
  const navigate = useNavigate();
  const [taxonomy, setTaxonomy] = useState<VaultTaxonomy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("tags");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedTags, setExpandedTags] = useState<Set<string>>(new Set());

  // Context menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    target: string;
    type: "tag" | "folder" | "link";
  } | null>(null);

  // Modal state
  const [modalOp, setModalOp] = useState<ModalOp | null>(null);
  const [modalTarget, setModalTarget] = useState("");
  const [modalValue, setModalValue] = useState("");
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const scan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVaultTaxonomy();
      setTaxonomy(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    scan();
  }, [scan]);

  // Dismiss context menu on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setContextMenu(null);
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const toggleTag = useCallback((name: string) => {
    setExpandedTags((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const openModal = useCallback((op: ModalOp, target = "") => {
    setModalOp(op);
    setModalTarget(target);
    setModalValue("");
    setModalError(null);
  }, []);

  const closeModal = useCallback(() => {
    setModalOp(null);
    setModalTarget("");
    setModalValue("");
    setModalError(null);
    setModalLoading(false);
  }, []);

  const submitModal = useCallback(async () => {
    if (!modalOp || !modalTarget.trim()) return;
    if (needsValue(modalOp) && !modalValue.trim()) return;

    setModalLoading(true);
    setModalError(null);
    try {
      const op: TaxonomyCurationOp = {
        op: modalOp as TaxonomyCurationOpType,
        target: modalTarget.trim(),
      };
      if (needsValue(modalOp)) op.value = modalValue.trim();
      const res = await applyTaxonomyCuration([op]);
      closeModal();
      navigate(`/changesets/${res.changeset_id}`);
    } catch (e) {
      setModalError(e instanceof Error ? e.message : String(e));
    } finally {
      setModalLoading(false);
    }
  }, [modalOp, modalTarget, modalValue, closeModal, navigate]);

  const handleContextMenu = useCallback(
    (e: React.MouseEvent, target: string, type: "tag" | "folder" | "link") => {
      e.preventDefault();
      setContextMenu({ x: e.clientX, y: e.clientY, target, type });
    },
    [],
  );

  // Filter tags
  const filteredTags =
    taxonomy?.tags.filter((t) =>
      t.name.toLowerCase().includes(searchQuery.toLowerCase()),
    ) ?? [];

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-muted">
          <RefreshIcon spinning />
          <span className="text-sm">Scanning vault taxonomy...</span>
        </div>
      </div>
    );
  }

  // Error state (no data)
  if (error && !taxonomy) {
    return (
      <div className="py-6 px-8">
        <ErrorAlert message={error} />
      </div>
    );
  }

  const TABS: Tab[] = ["folders", "tags", "links"];

  return (
    <div
      className="flex flex-col flex-1 min-h-0"
      onContextMenu={(e) => e.preventDefault()}
    >
      {/* Header bar */}
      <div className="px-6 py-4 flex items-center justify-between shrink-0">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
          Taxonomy Management
        </h2>
        <button
          onClick={scan}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted hover:text-text bg-transparent border border-white/10 rounded-md cursor-pointer transition-colors disabled:opacity-50"
        >
          <RefreshIcon spinning={loading} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="px-6 shrink-0">
          <ErrorAlert message={error} />
        </div>
      )}

      {/* Tab bar */}
      <div className="px-6 shrink-0">
        <div className="flex gap-1 bg-surface rounded-lg p-1 self-start w-fit">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className={`px-4 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer border-none ${
                activeTab === t
                  ? "bg-accent/15 text-accent"
                  : "bg-transparent text-muted hover:text-text"
              }`}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>
      </div>

      {/* Main grid — fills remaining height */}
      <div className="flex-1 overflow-y-auto px-6 pb-4 min-h-0">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 min-h-full">
          {/* Left panel — 2 cols */}
          <div className="md:col-span-2 glass-card p-4 flex flex-col gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
              {activeTab === "folders"
                ? "Folder Paths"
                : activeTab === "tags"
                  ? "Tag Hierarchy"
                  : "Link Targets"}
            </h3>

            {/* Search for tags tab */}
            {activeTab === "tags" && (
              <input
                type="text"
                placeholder="Filter tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-1.5 text-xs bg-elevated/50 border border-white/10 rounded-md text-text placeholder:text-muted/50 outline-none focus:border-accent/50"
              />
            )}

            <div className="flex flex-col gap-0.5 flex-1 overflow-y-auto">
              {/* Folders */}
              {activeTab === "folders" &&
                taxonomy?.folders.map((f) => {
                  const isHighlighted =
                    contextMenu?.type === "folder" && contextMenu.target === f;
                  return (
                    <div
                      key={f}
                      className={`flex items-center gap-2 py-1.5 px-2 rounded transition-colors ${
                        isHighlighted
                          ? "bg-orange/10 ring-1 ring-orange/40"
                          : "hover:bg-elevated/50"
                      }`}
                      onContextMenu={(e) => handleContextMenu(e, f, "folder")}
                    >
                      <FolderIcon />
                      <span className="text-xs font-mono text-text">{f}</span>
                    </div>
                  );
                })}

              {/* Tags — hierarchy */}
              {activeTab === "tags" &&
                !searchQuery &&
                taxonomy?.tag_hierarchy.map((node) => (
                  <TagTreeNode
                    key={node.name}
                    node={node}
                    depth={0}
                    expanded={expandedTags}
                    onToggle={toggleTag}
                    filter=""
                    onContextMenu={(e, name) =>
                      handleContextMenu(e, name, "tag")
                    }
                    highlightedTag={
                      contextMenu?.type === "tag" ? contextMenu.target : null
                    }
                  />
                ))}

              {/* Tags — filtered flat list with counts */}
              {activeTab === "tags" &&
                searchQuery &&
                filteredTags.map((t) => {
                  const isHighlighted =
                    contextMenu?.type === "tag" &&
                    contextMenu.target === t.name;
                  return (
                    <div
                      key={t.name}
                      className={`flex items-center justify-between py-1.5 px-2 rounded transition-colors ${
                        isHighlighted
                          ? "bg-orange/10 ring-1 ring-orange/40"
                          : "hover:bg-elevated/50"
                      }`}
                      onContextMenu={(e) => handleContextMenu(e, t.name, "tag")}
                    >
                      <span className="text-xs font-mono text-text">
                        {t.name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">
                        {t.count}
                      </span>
                    </div>
                  );
                })}

              {/* Tags — empty filter state */}
              {activeTab === "tags" &&
                searchQuery &&
                filteredTags.length === 0 && (
                  <span className="text-xs text-muted py-2">
                    No tags match "{searchQuery}"
                  </span>
                )}

              {/* Link targets */}
              {activeTab === "links" &&
                taxonomy &&
                [...taxonomy.link_targets]
                  .sort((a, b) => b.count - a.count)
                  .map((lt) => {
                    const isHighlighted =
                      contextMenu?.type === "link" &&
                      contextMenu.target === lt.title;
                    return (
                      <div
                        key={lt.title}
                        className={`flex items-center justify-between py-1.5 px-2 rounded transition-colors ${
                          isHighlighted
                            ? "bg-orange/10 ring-1 ring-orange/40"
                            : "hover:bg-elevated/50"
                        }`}
                        onContextMenu={(e) =>
                          handleContextMenu(e, lt.title, "link")
                        }
                      >
                        <span className="text-xs text-text">{lt.title}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/10 text-accent">
                          {lt.count}
                        </span>
                      </div>
                    );
                  })}
            </div>
          </div>

          {/* Right panel — stats */}
          <div className="flex flex-col gap-4">
            <div className="glass-card p-4 flex flex-col gap-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
                Vault Overview
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="stat-value">
                    {taxonomy?.total_notes ?? 0}
                  </span>
                  <span className="block text-[10px] text-muted mt-1">
                    Total Notes
                  </span>
                </div>
                <div>
                  <span className="stat-value">
                    {taxonomy?.tags.length ?? 0}
                  </span>
                  <span className="block text-[10px] text-muted mt-1">
                    Unique Tags
                  </span>
                </div>
                <div>
                  <span className="stat-value">
                    {taxonomy?.folders.length ?? 0}
                  </span>
                  <span className="block text-[10px] text-muted mt-1">
                    Folders
                  </span>
                </div>
                <div>
                  <span className="stat-value">
                    {taxonomy?.link_targets.length ?? 0}
                  </span>
                  <span className="block text-[10px] text-muted mt-1">
                    Link Targets
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Context menu */}
      {contextMenu && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setContextMenu(null)}
          onContextMenu={(e) => {
            e.preventDefault();
            setContextMenu(null);
          }}
        >
          <div
            className="fixed z-50 bg-surface border border-white/10 rounded-lg shadow-xl py-1 min-w-[160px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
            onClick={(e) => e.stopPropagation()}
          >
            {contextMenu.type === "tag" && (
              <>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
                  onClick={() => {
                    openModal("rename_tag", contextMenu.target);
                    setContextMenu(null);
                  }}
                >
                  Rename Tag
                </button>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
                  onClick={() => {
                    openModal("merge_tags", contextMenu.target);
                    setContextMenu(null);
                  }}
                >
                  Merge Tags
                </button>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs text-red hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
                  onClick={() => {
                    openModal("delete_tag", contextMenu.target);
                    setContextMenu(null);
                  }}
                >
                  Delete Tag
                </button>
              </>
            )}
            {contextMenu.type === "folder" && (
              <button
                className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
                onClick={() => {
                  openModal("rename_folder", contextMenu.target);
                  setContextMenu(null);
                }}
              >
                Rename Folder
              </button>
            )}
            {contextMenu.type === "link" && (
              <>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
                  onClick={() => {
                    openModal("rename_link", contextMenu.target);
                    setContextMenu(null);
                  }}
                >
                  Rename Link
                </button>
                <button
                  className="w-full text-left px-3 py-1.5 text-xs text-text hover:bg-elevated/50 bg-transparent border-none cursor-pointer"
                  onClick={() => {
                    openModal("merge_links", contextMenu.target);
                    setContextMenu(null);
                  }}
                >
                  Merge Links
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Curation modal */}
      {modalOp && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={closeModal}
        >
          <div
            className="glass-card p-6 w-full max-w-md flex flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-sm font-semibold text-text">
              {OP_LABELS[modalOp]}
            </h3>

            {modalError && <ErrorAlert message={modalError} />}

            <div className="flex flex-col gap-1">
              <label className="text-[11px] text-muted">Target</label>
              <input
                type="text"
                value={modalTarget}
                onChange={(e) => setModalTarget(e.target.value)}
                placeholder={
                  activeTab === "tags"
                    ? "#tag-name"
                    : activeTab === "folders"
                      ? "folder/path"
                      : "Link Title"
                }
                className="px-3 py-2 text-xs bg-elevated/50 border border-white/10 rounded-md text-text placeholder:text-muted/50 outline-none focus:border-accent/50"
              />
            </div>

            {needsValue(modalOp) && (
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-muted">
                  {modalOp.includes("merge") ? "Merge into" : "New name"}
                </label>
                <input
                  type="text"
                  value={modalValue}
                  onChange={(e) => setModalValue(e.target.value)}
                  placeholder={
                    modalOp.includes("merge")
                      ? "Target to merge into"
                      : "New name"
                  }
                  className="px-3 py-2 text-xs bg-elevated/50 border border-white/10 rounded-md text-text placeholder:text-muted/50 outline-none focus:border-accent/50"
                />
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={closeModal}
                className="px-4 py-2 text-xs text-muted hover:text-text bg-transparent border border-white/10 rounded-md cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={submitModal}
                disabled={
                  modalLoading ||
                  !modalTarget.trim() ||
                  (needsValue(modalOp) && !modalValue.trim())
                }
                className="btn-gradient text-xs py-2 px-4 disabled:opacity-50"
              >
                {modalLoading ? "Applying..." : "Apply"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
