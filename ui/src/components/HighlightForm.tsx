import { useState } from "react";
import type { HighlightInput } from "../types";

interface Props {
  onSubmit: (highlight: HighlightInput) => void;
  disabled: boolean;
}

export function HighlightForm({ onSubmit, disabled }: Props) {
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [annotation, setAnnotation] = useState("");
  const [tags, setTags] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !source.trim()) return;

    const parsedTags = tags.split(",").map((t) => t.trim()).filter(Boolean);
    onSubmit({
      text: text.trim(),
      source: source.trim(),
      annotation: annotation.trim() || undefined,
      tags: parsedTags.length > 0 ? parsedTags : undefined,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-surface border border-border rounded p-5 mb-5"
    >
      <h2 className="text-base mb-4">New Highlight</h2>

      <label className="block mb-3">
        <span className="block text-[13px] text-muted mb-1">
          Highlighted Text *
        </span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the highlighted text..."
          rows={4}
          required
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
          required
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

      <label className="block mb-3">
        <span className="block text-[13px] text-muted mb-1">Tags</span>
        <input
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="tag1, tag2, tag3"
          disabled={disabled}
          className="w-full bg-bg border border-border rounded text-text py-2 px-3 text-sm font-sans resize-y focus:outline-none focus:border-accent"
        />
      </label>

      <button
        type="submit"
        disabled={disabled || !text.trim() || !source.trim()}
        className="bg-accent text-white border-none py-2 px-5 rounded text-sm cursor-pointer font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {disabled ? "Generating preview..." : "Preview Changes"}
      </button>
    </form>
  );
}
