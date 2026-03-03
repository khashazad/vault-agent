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

    onSubmit({
      text: text.trim(),
      source: source.trim(),
      annotation: annotation.trim() || undefined,
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean) || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="highlight-form">
      <h2>New Highlight</h2>

      <label>
        <span>Highlighted Text *</span>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the highlighted text..."
          rows={4}
          required
          disabled={disabled}
        />
      </label>

      <label>
        <span>Source *</span>
        <input
          type="text"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="URL or document title"
          required
          disabled={disabled}
        />
      </label>

      <label>
        <span>Your Note</span>
        <textarea
          value={annotation}
          onChange={(e) => setAnnotation(e.target.value)}
          placeholder="Optional annotation..."
          rows={2}
          disabled={disabled}
        />
      </label>

      <label>
        <span>Tags</span>
        <input
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="tag1, tag2, tag3"
          disabled={disabled}
        />
      </label>

      <button type="submit" disabled={disabled || !text.trim() || !source.trim()}>
        {disabled ? "Processing..." : "Process Highlight"}
      </button>
    </form>
  );
}
