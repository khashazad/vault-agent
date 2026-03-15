import { useState } from "react";
import type { PassageAnnotation } from "../types";

interface Props {
  annotations: PassageAnnotation[];
  onAdd: (annotation: PassageAnnotation) => void;
  onRemove: (id: string) => void;
  onSubmit: () => void;
  submitting: boolean;
}

export function formatAnnotations(annotations: PassageAnnotation[]): string {
  return annotations
    .map((a) => `[Passage: "${a.selectedText}"]\nFeedback: ${a.comment}`)
    .join("\n\n");
}

export function AnnotationFeedback({
  annotations,
  onAdd,
  onRemove,
  onSubmit,
  submitting,
}: Props) {
  const [comment, setComment] = useState("");
  const [selectedText, setSelectedText] = useState("");
  const [hint, setHint] = useState<string | null>(null);

  const handleCapture = () => {
    const sel = window.getSelection()?.toString().trim();
    if (!sel) {
      setHint("Select text in the preview first");
      return;
    }
    setSelectedText(sel);
    setHint(null);
  };

  const handleAdd = () => {
    if (!selectedText.trim() || !comment.trim()) return;
    onAdd({
      id: crypto.randomUUID(),
      selectedText: selectedText.trim(),
      comment: comment.trim(),
    });
    setComment("");
    setSelectedText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="bg-surface border border-border rounded p-4 flex flex-col gap-3">
      <h4 className="text-sm font-medium m-0">Request Changes</h4>

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={handleCapture}
          className="self-start text-xs bg-elevated text-text border border-border py-1.5 px-3 rounded cursor-pointer hover:border-accent transition-colors"
        >
          Annotate Selection
        </button>
        {hint && <span className="text-xs text-yellow">{hint}</span>}
      </div>

      {selectedText && (
        <div className="flex flex-col gap-2">
          <div className="bg-bg border border-border rounded p-2 text-xs text-muted italic">
            &ldquo;{selectedText}&rdquo;
          </div>
          <input
            type="text"
            className="w-full bg-bg border border-border rounded p-2 text-sm text-foreground outline-none focus:border-accent"
            placeholder="What should change?"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={!comment.trim()}
            className="self-start text-xs bg-accent text-crust border-none py-1.5 px-3 rounded cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add
          </button>
        </div>
      )}

      {annotations.length > 0 && (
        <div className="flex flex-col gap-2 mt-1">
          {annotations.map((a) => (
            <div
              key={a.id}
              className="bg-bg border border-border rounded p-2 flex items-start gap-2"
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs text-muted italic m-0 mb-1 truncate">
                  &ldquo;{a.selectedText}&rdquo;
                </p>
                <p className="text-sm m-0">{a.comment}</p>
              </div>
              <button
                type="button"
                onClick={() => onRemove(a.id)}
                className="text-red bg-transparent border-none cursor-pointer text-xs p-0 leading-none flex-shrink-0"
                title="Remove"
                aria-label="Remove annotation"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onSubmit}
        disabled={submitting || annotations.length === 0}
        className="self-start bg-accent text-crust border-none py-2 px-5 rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting
          ? "Submitting..."
          : `Request Changes (${annotations.length})`}
      </button>
    </div>
  );
}
