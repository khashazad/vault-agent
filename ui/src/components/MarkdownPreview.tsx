import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
import type { Components } from "react-markdown";
import { extractFrontmatter, preprocessObsidian } from "../utils/obsidian";

interface Props {
  content: string;
}

function FrontmatterBar({
  frontmatter,
}: {
  frontmatter: Record<string, unknown>;
}) {
  return (
    <div className="frontmatter-bar">
      {Object.entries(frontmatter).map(([key, value]) => {
        const display =
          typeof value === "string"
            ? value
            : Array.isArray(value)
              ? value.join(", ")
              : String(value ?? "");
        if (!display) return null;
        return (
          <div key={key} className="flex items-center gap-1">
            <span className="frontmatter-key">{key}:</span>
            <span className="frontmatter-value">{display}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Map Obsidian callout aliases to canonical types */
const CALLOUT_ALIASES: Record<string, string> = {
  summary: "abstract",
  tldr: "abstract",
  hint: "tip",
  important: "tip",
  check: "success",
  done: "success",
  help: "question",
  faq: "question",
  caution: "warning",
  attention: "warning",
  fail: "failure",
  missing: "failure",
  cite: "quote",
  error: "danger",
};

/** Parse callout type from blockquote content like "[!note]+ Title" */
function parseCallout(children: React.ReactNode): {
  type: string;
  title: string;
  fold: "+" | "-" | null;
  body: React.ReactNode[];
} | null {
  const childArray = Array.isArray(children) ? children : [children];
  // The first child paragraph typically contains "[!type] Title"
  const first = childArray[0];
  if (!first || typeof first !== "object" || !("props" in first)) return null;

  const props = first.props as { children?: React.ReactNode };
  const innerChildren = Array.isArray(props.children)
    ? props.children
    : [props.children];
  const firstText =
    typeof innerChildren[0] === "string" ? innerChildren[0] : null;
  if (!firstText) return null;

  const match = firstText.match(/^\[!(\w+)\]([+-])?\s*(.*)/);
  if (!match) return null;

  const rawType = match[1].toLowerCase();
  const type = CALLOUT_ALIASES[rawType] ?? rawType;
  const fold = (match[2] as "+" | "-") ?? null;
  const title = match[3] || rawType;
  // Remaining text after the callout marker in the same paragraph
  const remainingInline = innerChildren.slice(1);
  const restParagraph =
    remainingInline.length > 0 || firstText.length > match[0].length
      ? remainingInline
      : [];
  const restChildren = childArray.slice(1);

  return { type, title, fold, body: [...restParagraph, ...restChildren] };
}

const components: Components = {
  blockquote({ children }) {
    const callout = parseCallout(children);
    if (callout) {
      const bodyContent =
        callout.body.length > 0 ? <div>{callout.body}</div> : null;

      // Foldable callout
      if (callout.fold) {
        return (
          <details
            className={`callout callout-${callout.type} callout-foldable`}
            open={callout.fold === "+"}
          >
            <summary className="callout-title">{callout.title}</summary>
            {bodyContent}
          </details>
        );
      }

      return (
        <div className={`callout callout-${callout.type}`}>
          <div className="callout-title">{callout.title}</div>
          {bodyContent}
        </div>
      );
    }
    return <blockquote>{children}</blockquote>;
  },
};

export function MarkdownPreview({ content }: Props) {
  const { frontmatter, body } = extractFrontmatter(content);
  const processed = preprocessObsidian(body);

  return (
    <div className="border border-border rounded overflow-hidden bg-bg p-4">
      {frontmatter && <FrontmatterBar frontmatter={frontmatter} />}
      <div className="markdown-preview">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[
            [rehypeRaw, { passThrough: ["math", "inlineMath"] }],
            rehypeKatex,
          ]}
          components={components}
        >
          {processed}
        </ReactMarkdown>
      </div>
    </div>
  );
}
