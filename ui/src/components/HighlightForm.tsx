import { useState } from "react";
import type { HighlightInput } from "../types";

interface Props {
  onSubmit: (highlights: HighlightInput[]) => void;
  disabled: boolean;
}

export function HighlightForm({ onSubmit, disabled }: Props) {
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [annotation, setAnnotation] = useState("");
  const [batch, setBatch] = useState<HighlightInput[]>([]);

  const buildHighlight = (): HighlightInput | null => {
    if (!text.trim() || !source.trim()) return null;
    return {
      text: text.trim(),
      source: source.trim(),
      annotation: annotation.trim() || undefined,
    };
  };

  const clearForm = () => {
    setText("");
    setAnnotation("");
    // Keep source — likely the same for batch items
  };

  const handleAddToBatch = () => {
    const h = buildHighlight();
    if (!h) return;
    setBatch((prev) => [...prev, h]);
    clearForm();
  };

  const handleRemoveFromBatch = (index: number) => {
    setBatch((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const current = buildHighlight();
    const highlights = current ? [...batch, current] : [...batch];
    if (highlights.length === 0) return;
    onSubmit(highlights);
    setBatch([]);
    clearForm();
    setSource("");
  };

  const canAdd = text.trim() && source.trim();
  const canSubmit = batch.length > 0 || canAdd;

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-surface border border-border rounded p-5"
    >
      <h2 className="text-base mb-4">New Snippet</h2>

      {batch.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[13px] text-muted uppercase tracking-wide mb-2">
            Queued ({batch.length})
          </h4>
          <div className="flex flex-col gap-1.5">
            {batch.map((h, i) => (
              <div
                key={i}
                className="flex items-start gap-2 bg-bg border border-border rounded py-2 px-3 text-sm"
              >
                <span className="flex-1 line-clamp-2">{h.text}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveFromBatch(i)}
                  className="text-muted hover:text-red shrink-0 text-xs"
                >
                  remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <label className="block mb-3">
        <span className="block text-[13px] text-muted mb-1">
          Snippet *
        </span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the snippet..."
          rows={4}
          required={batch.length === 0}
          disabled={disabled}
          className="w-full bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y focus:outline-none focus:border-accent"
        />
      </label>

      <label className="block mb-3">
        <span className="block text-[13px] text-muted mb-1">Source *</span>
        <input
          type="text"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="URL or document title"
          required={batch.length === 0}
          disabled={disabled}
          className="w-full bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y focus:outline-none focus:border-accent"
        />
      </label>

      <label className="block mb-3">
        <span className="block text-[13px] text-muted mb-1">Your Note</span>
        <textarea
          value={annotation}
          onChange={(e) => setAnnotation(e.target.value)}
          placeholder="Optional annotation..."
          rows={2}
          disabled={disabled}
          className="w-full bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y focus:outline-none focus:border-accent"
        />
      </label>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleAddToBatch}
          disabled={disabled || !canAdd}
          className="bg-elevated text-text border border-border py-2 px-5 rounded text-sm cursor-pointer font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add to Batch
        </button>
        <button
          type="submit"
          disabled={disabled || !canSubmit}
          className="bg-accent text-crust border-none py-2 px-5 rounded text-sm cursor-pointer font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {disabled
            ? "Generating preview..."
            : batch.length > 0
              ? `Preview ${batch.length + (canAdd ? 1 : 0)} Snippets`
              : "Preview Changes"}
        </button>
      </div>
    </form>
  );
}
