// Minimal Markdown renderer.
//
// We deliberately don't pull in a full Markdown library — the dialect
// is small enough that a hand-rolled renderer keeps total surface
// area tiny and makes "what shows up on the page" obvious from the
// component code. Supported syntax:
//
//   ## heading                  → <h2>
//   ### heading                 → <h3>
//   - bullet                    → <ul><li>...</li></ul>
//   > pull quote                → <blockquote>
//   [label](https://url)        → inline anchor
//   **bold**                    → <strong>
//   blank line                  → paragraph break
//
// Anything else is rendered as a paragraph.

import { Fragment } from "react";

interface Props {
  body: string;
}

export function ArticleBody({ body }: Props) {
  const blocks = parseBlocks(body);
  return (
    <div className="prose prose-stone dark:prose-invert max-w-none editorial">
      {blocks.map((b, i) => renderBlock(b, i))}
    </div>
  );
}

type Block =
  | { kind: "h2"; text: string }
  | { kind: "h3"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "p"; text: string };

function parseBlocks(body: string): Block[] {
  const lines = body.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push({ kind: "h2", text: line.slice(3).trim() });
      i++;
    } else if (line.startsWith("### ")) {
      blocks.push({ kind: "h3", text: line.slice(4).trim() });
      i++;
    } else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) {
        items.push(lines[i].slice(2).trim());
        i++;
      }
      blocks.push({ kind: "ul", items });
    } else if (line.startsWith("> ")) {
      blocks.push({ kind: "quote", text: line.slice(2).trim() });
      i++;
    } else {
      // Gather a paragraph: consecutive non-empty, non-special lines.
      const buf: string[] = [];
      while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      blocks.push({ kind: "p", text: buf.join(" ") });
    }
  }
  return blocks;
}

function isBlockStart(line: string): boolean {
  return (
    line.startsWith("## ") ||
    line.startsWith("### ") ||
    line.startsWith("- ") ||
    line.startsWith("> ")
  );
}

function renderBlock(block: Block, key: number): React.ReactNode {
  switch (block.kind) {
    case "h2":
      return (
        <h2 key={key} className="editorial mt-10 text-2xl font-semibold md:text-3xl">
          {renderInline(block.text)}
        </h2>
      );
    case "h3":
      return (
        <h3 key={key} className="mt-6 text-xl font-semibold">
          {renderInline(block.text)}
        </h3>
      );
    case "ul":
      return (
        <ul key={key} className="mt-3 list-disc pl-5 space-y-1.5">
          {block.items.map((it, j) => (
            <li key={j}>{renderInline(it)}</li>
          ))}
        </ul>
      );
    case "quote":
      return (
        <blockquote
          key={key}
          className="my-6 border-l-2 border-primary/40 pl-4 italic text-foreground/85"
        >
          {renderInline(block.text)}
        </blockquote>
      );
    case "p":
      return (
        <p key={key} className="mt-4 leading-relaxed">
          {renderInline(block.text)}
        </p>
      );
  }
}

// Inline renderer — links + bold. We process bold first by a regex
// split, then run links over each non-bold span. Order matters
// because a link can wrap bold text.
function renderInline(text: string): React.ReactNode {
  const linkRe = /\[([^\]]+)\]\(([^)]+)\)/g;
  const boldRe = /\*\*([^*]+)\*\*/g;
  // First, walk the link matches and split.
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = linkRe.exec(text)) !== null) {
    if (m.index > lastIndex) {
      parts.push(
        <Fragment key={key++}>{renderBold(text.slice(lastIndex, m.index))}</Fragment>,
      );
    }
    parts.push(
      <a
        key={key++}
        href={m[2]}
        target={m[2].startsWith("http") ? "_blank" : undefined}
        rel={m[2].startsWith("http") ? "noreferrer" : undefined}
        className="text-primary underline-offset-2 hover:underline"
      >
        {renderBold(m[1])}
      </a>,
    );
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(
      <Fragment key={key++}>{renderBold(text.slice(lastIndex))}</Fragment>,
    );
  }
  return parts;

  function renderBold(s: string): React.ReactNode {
    const out: React.ReactNode[] = [];
    let last = 0;
    let n: RegExpExecArray | null;
    let bk = 0;
    boldRe.lastIndex = 0;
    while ((n = boldRe.exec(s)) !== null) {
      if (n.index > last) out.push(<Fragment key={bk++}>{s.slice(last, n.index)}</Fragment>);
      out.push(<strong key={bk++}>{n[1]}</strong>);
      last = n.index + n[0].length;
    }
    if (last < s.length) out.push(<Fragment key={bk++}>{s.slice(last)}</Fragment>);
    return out;
  }
}
