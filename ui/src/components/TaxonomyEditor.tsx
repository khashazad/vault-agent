import { useState } from "react";
import type { TaxonomyProposal, TagNode, LinkTarget } from "../types";

interface Props {
  taxonomy: TaxonomyProposal;
  onSave: (updates: Partial<TaxonomyProposal>) => Promise<void>;
  onActivate: () => Promise<void>;
}

export function TaxonomyEditor({ taxonomy, onSave, onActivate }: Props) {
  const [folders, setFolders] = useState<string[]>(taxonomy.folders);
  const [tagHierarchy, setTagHierarchy] = useState<TagNode[]>(
    taxonomy.tag_hierarchy,
  );
  const [linkTargets, setLinkTargets] = useState<LinkTarget[]>(
    taxonomy.link_targets,
  );
  const [newFolder, setNewFolder] = useState("");
  const [saving, setSaving] = useState(false);
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await onSave({
        folders,
        tag_hierarchy: tagHierarchy,
        link_targets: linkTargets,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleActivate() {
    setActivating(true);
    setError(null);
    try {
      await onActivate();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setActivating(false);
    }
  }

  function addFolder() {
    const trimmed = newFolder.trim();
    if (!trimmed || folders.includes(trimmed)) return;
    setFolders([...folders, trimmed]);
    setNewFolder("");
  }

  function removeFolder(index: number) {
    setFolders(folders.filter((_, i) => i !== index));
  }

  function removeTag(hierarchy: TagNode[], target: TagNode): TagNode[] {
    return hierarchy
      .filter((node) => node !== target)
      .map((node) => ({
        ...node,
        children: removeTag(node.children, target),
      }));
  }

  function addTagAtRoot(name: string) {
    if (!name.trim()) return;
    setTagHierarchy([
      ...tagHierarchy,
      { name: name.trim(), children: [], description: null },
    ]);
  }

  function addChildTag(parent: TagNode, name: string) {
    if (!name.trim()) return;
    const child: TagNode = {
      name: name.trim(),
      children: [],
      description: null,
    };
    setTagHierarchy(
      tagHierarchy.map((node) => addChildToNode(node, parent, child)),
    );
  }

  function addChildToNode(
    node: TagNode,
    parent: TagNode,
    child: TagNode,
  ): TagNode {
    if (node === parent) {
      return { ...node, children: [...node.children, child] };
    }
    return {
      ...node,
      children: node.children.map((c) => addChildToNode(c, parent, child)),
    };
  }

  function updateLinkTarget(index: number, updates: Partial<LinkTarget>) {
    setLinkTargets(
      linkTargets.map((lt, i) => (i === index ? { ...lt, ...updates } : lt)),
    );
  }

  function addLinkTarget() {
    setLinkTargets([...linkTargets, { title: "", aliases: [], folder: "" }]);
  }

  function removeLinkTarget(index: number) {
    setLinkTargets(linkTargets.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Folders */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-muted uppercase tracking-wide">
          Folders
        </h3>
        <div className="space-y-1">
          {folders.map((folder, i) => (
            <div
              key={i}
              className="flex items-center justify-between rounded bg-surface px-3 py-1.5 text-sm"
            >
              <span className="font-mono">{folder}</span>
              <button
                onClick={() => removeFolder(i)}
                className="text-muted hover:text-red-400 transition-colors text-xs"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={newFolder}
            onChange={(e) => setNewFolder(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addFolder()}
            placeholder="folder/path"
            className="flex-1 rounded border border-border bg-surface px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
          />
          <button
            onClick={addFolder}
            className="rounded bg-accent/15 px-3 py-1.5 text-sm text-accent hover:bg-accent/25 transition-colors"
          >
            Add
          </button>
        </div>
      </section>

      {/* Tag Hierarchy */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-muted uppercase tracking-wide">
          Tag Hierarchy
        </h3>
        <TagList
          nodes={tagHierarchy}
          depth={0}
          onRemove={(node) => setTagHierarchy(removeTag(tagHierarchy, node))}
          onAddChild={addChildTag}
        />
        <AddTagInput onAdd={addTagAtRoot} placeholder="Add root tag" />
      </section>

      {/* Link Targets */}
      <section>
        <h3 className="mb-3 text-sm font-semibold text-muted uppercase tracking-wide">
          Link Targets
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="pb-2 pr-2 font-medium">Title</th>
                <th className="pb-2 pr-2 font-medium">Aliases</th>
                <th className="pb-2 pr-2 font-medium">Folder</th>
                <th className="pb-2 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {linkTargets.map((lt, i) => (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-1.5 pr-2">
                    <input
                      type="text"
                      value={lt.title}
                      onChange={(e) =>
                        updateLinkTarget(i, { title: e.target.value })
                      }
                      className="w-full rounded border border-border bg-surface px-2 py-1 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="text"
                      value={lt.aliases.join(", ")}
                      onChange={(e) =>
                        updateLinkTarget(i, {
                          aliases: e.target.value
                            .split(",")
                            .map((a) => a.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="alias1, alias2"
                      className="w-full rounded border border-border bg-surface px-2 py-1 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td className="py-1.5 pr-2">
                    <input
                      type="text"
                      value={lt.folder}
                      onChange={(e) =>
                        updateLinkTarget(i, { folder: e.target.value })
                      }
                      className="w-full rounded border border-border bg-surface px-2 py-1 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td className="py-1.5">
                    <button
                      onClick={() => removeLinkTarget(i)}
                      className="text-muted hover:text-red-400 transition-colors text-xs"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button
          onClick={addLinkTarget}
          className="mt-2 rounded bg-accent/15 px-3 py-1.5 text-sm text-accent hover:bg-accent/25 transition-colors"
        >
          Add link target
        </button>
      </section>

      {/* Actions */}
      <div className="flex gap-3 border-t border-border pt-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded bg-accent/15 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/25 transition-colors disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Changes"}
        </button>
        <button
          onClick={handleActivate}
          disabled={activating}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-surface hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {activating ? "Activating..." : "Activate & Start Migration"}
        </button>
      </div>
    </div>
  );
}

function TagList({
  nodes,
  depth,
  onRemove,
  onAddChild,
}: {
  nodes: TagNode[];
  depth: number;
  onRemove: (node: TagNode) => void;
  onAddChild: (parent: TagNode, name: string) => void;
}) {
  return (
    <div style={{ paddingLeft: depth * 16 }}>
      {nodes.map((node, i) => (
        <div key={`${node.name}-${i}`}>
          <div className="flex items-center gap-2 rounded px-2 py-1 hover:bg-surface group">
            <span className="text-sm">
              {depth > 0 && <span className="text-muted mr-1">{"/"}</span>}
              {node.name}
            </span>
            <button
              onClick={() => onRemove(node)}
              className="text-xs text-muted opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
            >
              Remove
            </button>
            <AddTagInline onAdd={(name) => onAddChild(node, name)} />
          </div>
          {node.children.length > 0 && (
            <TagList
              nodes={node.children}
              depth={depth + 1}
              onRemove={onRemove}
              onAddChild={onAddChild}
            />
          )}
        </div>
      ))}
    </div>
  );
}

function AddTagInput({
  onAdd,
  placeholder,
}: {
  onAdd: (name: string) => void;
  placeholder: string;
}) {
  const [value, setValue] = useState("");

  function submit() {
    if (!value.trim()) return;
    onAdd(value);
    setValue("");
  }

  return (
    <div className="mt-2 flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder={placeholder}
        className="flex-1 rounded border border-border bg-surface px-3 py-1.5 text-sm focus:border-accent focus:outline-none"
      />
      <button
        onClick={submit}
        className="rounded bg-accent/15 px-3 py-1.5 text-sm text-accent hover:bg-accent/25 transition-colors"
      >
        Add
      </button>
    </div>
  );
}

function AddTagInline({ onAdd }: { onAdd: (name: string) => void }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");

  function submit() {
    if (!value.trim()) return;
    onAdd(value);
    setValue("");
    setOpen(false);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-muted opacity-0 group-hover:opacity-100 hover:text-accent transition-all"
      >
        + child
      </button>
    );
  }

  return (
    <input
      autoFocus
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") submit();
        if (e.key === "Escape") setOpen(false);
      }}
      onBlur={() => {
        if (!value.trim()) setOpen(false);
      }}
      placeholder="child tag"
      className="rounded border border-border bg-surface px-2 py-0.5 text-xs focus:border-accent focus:outline-none w-28"
    />
  );
}
