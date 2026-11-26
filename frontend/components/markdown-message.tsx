"use client";

import { Children, isValidElement, type ReactNode, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";

function normalizeMarkdown(content: string) {
  const containsMarkdown = (markdown: string) =>
    /^\s{0,3}#{1,6}\s/m.test(markdown) ||
    /\*\*[^*\n]+\*\*/.test(markdown) ||
    /^[ \t]*(?:[-+*]|\d+[.)])\s+/m.test(markdown) ||
    /^\s*\|?.+\|.+\r?\n\s*\|?\s*:?-{3,}/m.test(markdown) ||
    /^\s*>/m.test(markdown) ||
    /\[[^\]]+\]\([^)]+\)/.test(markdown);

  const lines = content.match(/.*(?:\r?\n|$)/g)?.filter(Boolean) || [];
  let normalized = "";

  for (let index = 0; index < lines.length;) {
    const opening = /^[ \t]*```(markdown|md)?[ \t]*\r?\n$/i.exec(lines[index]);
    if (!opening) {
      normalized += lines[index];
      index += 1;
      continue;
    }

    let nestedFences = 0;
    let closing = -1;
    for (let cursor = index + 1; cursor < lines.length; cursor += 1) {
      if (/^[ \t]*```[^\s`][^\r\n]*\r?\n$/.test(lines[cursor])) {
        nestedFences += 1;
      } else if (/^[ \t]*```[ \t]*\r?\n?$/.test(lines[cursor])) {
        if (nestedFences > 0) nestedFences -= 1;
        else {
          closing = cursor;
          break;
        }
      }
    }

    const markdown = lines.slice(index + 1, closing === -1 ? undefined : closing).join("");
    const isWholeUnlabelledFence =
      !opening[1] &&
      index === 0 &&
      closing !== -1 &&
      lines.slice(closing + 1).every((line) => !line.trim());

    if (containsMarkdown(markdown) && (opening[1] || isWholeUnlabelledFence)) {
      normalized += markdown;
      index = closing === -1 ? lines.length : closing + 1;
    } else {
      normalized += lines[index];
      index += 1;
    }
  }

  return normalized;
}

function CodeBlock({ children }: { children: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const child = Children.toArray(children)[0];
  const language =
    isValidElement<{ className?: string; children?: ReactNode }>(child)
      ? /language-([\w-]+)/.exec(child.props.className || "")?.[1]
      : undefined;
  const codeText =
    isValidElement<{ children?: ReactNode }>(child) && child.props.children
      ? String(child.props.children).replace(/\n$/, "")
      : "";

  async function copyCode() {
    await navigator.clipboard.writeText(codeText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="code-frame">
      <div className="code-toolbar">
        <span className="code-language">{language || "Code"}</span>
        <button className="code-copy" type="button" onClick={copyCode} aria-label="Copy code">
          {copied ? <Check size={16} /> : <Copy size={16} />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
          code: ({ className, children, ...props }) => (
            <code className={className} {...props}>
              {children}
            </code>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {normalizeMarkdown(content)}
      </ReactMarkdown>
    </div>
  );
}
