import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
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
        if (key === "tags" && Array.isArray(value)) {
          return (
            <div key={key} className="flex items-center gap-1">
              <span className="frontmatter-key">{key}:</span>
              <span>
                {value.map((tag) => (
                  <span key={tag} className="frontmatter-tag">
                    {tag}
                  </span>
                ))}
              </span>
            </div>
          );
        }
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

/** Parse callout type from blockquote content like "[!note] Title" */
function parseCallout(children: React.ReactNode): {
  type: string;
  title: string;
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

  const match = firstText.match(/^\[!(\w+)\]\s*(.*)/);
  if (!match) return null;

  const type = match[1].toLowerCase();
  const title = match[2] || type;
  // Remaining text after the callout marker in the same paragraph
  const remainingInline = innerChildren.slice(1);
  const restParagraph =
    remainingInline.length > 0 || firstText.length > match[0].length
      ? remainingInline
      : [];
  const restChildren = childArray.slice(1);

  return { type, title, body: [...restParagraph, ...restChildren] };
}

const components: Components = {
  blockquote({ children }) {
    const callout = parseCallout(children);
    if (callout) {
      return (
        <div className={`callout callout-${callout.type}`}>
          <div className="callout-title">{callout.title}</div>
          {callout.body.length > 0 && <div>{callout.body}</div>}
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
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={components}
        >
          {processed}
        </ReactMarkdown>
      </div>
    </div>
  );
}
