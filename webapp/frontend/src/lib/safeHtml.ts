/**
 * Allowlist HTML -> React nodes, without `dangerouslySetInnerHTML`.
 *
 * Remote HTML (law articles, HR tips, a broadcast preview) is parsed with
 * `DOMParser` — an inert document: no script runs, no resource loads — and
 * then walked node by node. Only the tags a profile names become elements;
 * every other element is unwrapped so its text still reads (the contents of
 * `<script>`, `<style>` and friends are dropped), and no attribute is ever
 * copied except a validated `href`. Text reaches React as strings, so React
 * escapes it; nothing is re-serialized to an HTML string.
 */
import { createElement, Fragment, type ReactNode } from "react";

export type SafeTagSpec = {
  /** The element actually rendered (e.g. `b` -> `strong`). */
  as: string;
  className?: string;
};

export type SafeHtmlProfile = {
  /** Allowed source tags (lower-case) and how each renders. `a` and `br` are handled specially. */
  tags: Readonly<Record<string, SafeTagSpec>>;
  /** Allowed `href` protocols, lower-case with the colon (`"https:"`). */
  schemes: readonly string[];
};

/** Elements whose text content is not readable prose: dropped, not unwrapped. */
const DROP_CONTENT = new Set([
  "script", "style", "template", "noscript", "iframe", "object", "embed", "svg", "math", "title",
]);

/**
 * `true` when `raw` is an absolute URL whose protocol is allowlisted. The URL
 * parser applies the same tab/newline/control stripping a browser does, so
 * `java\tscript:` and `&#106;avascript:` (already decoded by `getAttribute`)
 * resolve to `javascript:` and fail; a relative path has no base and fails.
 */
export function safeHref(raw: string | null | undefined, schemes: readonly string[]): string | null {
  const value = (raw ?? "").trim();
  if (!value) return null;
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    return null;
  }
  return schemes.includes(url.protocol.toLowerCase()) ? url.href : null;
}

function renderChildren(parent: Node, profile: SafeHtmlProfile): ReactNode[] {
  const out: ReactNode[] = [];
  parent.childNodes.forEach((child, index) => {
    const node = renderNode(child, profile, index);
    if (node !== null) out.push(node);
  });
  return out;
}

function renderNode(node: Node, profile: SafeHtmlProfile, key: number): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.nodeValue ?? "";
  if (node.nodeType !== Node.ELEMENT_NODE) return null;

  const element = node as Element;
  const tag = element.localName.toLowerCase();
  if (DROP_CONTENT.has(tag)) return null;

  const spec = profile.tags[tag];
  if (tag === "br" && spec) return createElement("br", { key });

  const children = renderChildren(element, profile);
  if (!spec) return createElement(Fragment, { key }, ...children);

  if (tag === "a") {
    const href = safeHref(element.getAttribute("href"), profile.schemes);
    // A link we will not follow still keeps its text, so the paragraph reads.
    if (!href) return createElement(Fragment, { key }, ...children);
    return createElement(
      "a",
      { key, href, target: "_blank", rel: "noopener noreferrer", className: spec.className },
      ...children,
    );
  }

  return createElement(spec.as, { key, className: spec.className }, ...children);
}

/** Parses `html` and returns the allowlisted React nodes (an empty list for empty input). */
export function renderSafeHtml(html: string | null | undefined, profile: SafeHtmlProfile): ReactNode[] {
  const source = html ?? "";
  if (!source) return [];
  const doc = new DOMParser().parseFromString(source, "text/html");
  return renderChildren(doc.body, profile);
}

/**
 * Law articles / HR tips: exactly the backend content allowlist
 * (`webapp/routers/admin_content.py`): `<b> <i> <u> <code> <br> <a href>`,
 * links http/https/tg/mailto.
 */
export const CONTENT_HTML: SafeHtmlProfile = {
  tags: {
    b: { as: "strong" },
    i: { as: "em" },
    u: { as: "u" },
    code: { as: "code", className: "rounded bg-surfaceAlt px-1 font-mono" },
    br: { as: "br" },
    a: { as: "a", className: "text-primary underline" },
  },
  schemes: ["http:", "https:", "tg:", "mailto:"],
};

/** Telegram's HTML subset (`admin_broadcasts.py:ALLOWED_TAGS`), for the broadcast preview. */
export const TELEGRAM_HTML: SafeHtmlProfile = {
  tags: {
    b: { as: "b" },
    strong: { as: "strong" },
    i: { as: "i" },
    em: { as: "em" },
    u: { as: "u" },
    ins: { as: "ins" },
    s: { as: "s" },
    strike: { as: "s" },
    del: { as: "del" },
    code: { as: "code" },
    pre: { as: "pre" },
    blockquote: { as: "blockquote" },
    span: { as: "span" },
    "tg-spoiler": { as: "span" },
    br: { as: "br" },
    a: { as: "a" },
  },
  schemes: ["http:", "https:", "tg:"],
};
