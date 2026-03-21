import { useState } from "react";
import { MarkdownPreview } from "../components/MarkdownPreview";

const SAMPLE_FRONTMATTER = {
  tags: ["ml", "transformers", "attention"],
  source: "Vaswani et al., 2017",
  created: "2025-01-15",
};

const SAMPLE_CONTENT = `---
tags: [ml, transformers, attention]
source: "Vaswani et al., 2017"
created: 2025-01-15
---

# Attention Is All You Need

## Key Contributions

The paper introduces the **Transformer** architecture, which relies entirely on [[attention mechanisms]] to draw global dependencies between input and output, dispensing with recurrence and convolutions entirely.

> The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder.

## Architecture

The Transformer follows an encoder-decoder structure using stacked self-attention and point-wise, fully connected layers:

- **Multi-Head Attention**: Allows the model to jointly attend to information from different representation subspaces
- **Positional Encoding**: Since the model contains no recurrence, positional encodings are added to give the model information about token positions
- **Feed-Forward Networks**: Applied to each position separately and identically

## Results

The model achieved **28.4 BLEU** on the WMT 2014 English-to-German translation task, surpassing existing best results including ensembles by over 2 BLEU.

> [!note] Impact
> This paper is widely considered one of the most influential in modern deep learning, forming the basis for #research/ai models like [[BERT]], [[GPT-4]], and all modern LLMs.

## Related Notes

- [[Self-Attention Mechanism]]
- [[Positional Encoding]]
- [[BERT]]
`;

export function PreviewPage() {
  const [showFrontmatter, setShowFrontmatter] = useState(true);

  return (
    <div className="flex flex-col gap-4 max-w-4xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="uppercase tracking-wide">Vault</span>
        <span>&rsaquo;</span>
        <span className="text-text font-medium">Attention Is All You Need</span>
      </div>

      {/* Title + badges */}
      <div className="flex items-center gap-3">
        <h1 className="text-lg font-bold m-0">Attention Is All You Need</h1>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-bg text-green font-medium">
          Validated
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-surface border border-border text-muted">
          v1.2
        </span>
      </div>

      {/* Frontmatter toggle */}
      <button
        onClick={() => setShowFrontmatter(!showFrontmatter)}
        className="self-start text-xs text-muted bg-transparent border border-border rounded px-3 py-1 cursor-pointer hover:border-accent hover:text-accent transition-colors"
      >
        {showFrontmatter ? "Hide" : "Show"} Frontmatter
      </button>

      {showFrontmatter && (
        <div className="glass-card p-4 flex flex-wrap gap-4">
          {Object.entries(SAMPLE_FRONTMATTER).map(([key, value]) => (
            <div key={key} className="flex flex-col gap-0.5">
              <span className="text-[10px] text-muted font-mono uppercase">
                {key}
              </span>
              <span className="text-xs text-text font-mono">
                {Array.isArray(value) ? value.join(", ") : value}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Markdown content */}
      <div className="glass-card p-6">
        <MarkdownPreview content={SAMPLE_CONTENT} />
      </div>

      {/* Bottom actions */}
      <div className="sticky bottom-6 flex justify-end gap-3">
        <button className="text-xs px-5 py-2.5 rounded-lg bg-surface border border-border text-muted cursor-pointer hover:text-text hover:border-accent transition-colors">
          Edit Markdown
        </button>
        <button className="btn-gradient text-xs">Approve</button>
      </div>
    </div>
  );
}
