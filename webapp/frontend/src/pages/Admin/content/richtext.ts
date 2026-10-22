/**
 * Client-side mirror of the backend's strict HTML allowlist scanner
 * (`webapp/routers/admin_content.py:_html_is_valid`): `<b> <i> <u> <a href> <code> <br>`
 * only, no other attributes, tags must balance. Used to (a) give an inline
 * "invalid markup" hint before the user hits Save and (b) render a safe
 * preview without `dangerouslySetInnerHTML`.
 *
 * This is deliberately a parser, not a sanitizer: invalid input renders
 * nothing (the caller shows a fallback message) rather than being cleaned up,
 * matching the backend's fail-closed behaviour.
 */

export const ALLOWED_TAGS = new Set(["b", "i", "u", "a", "code", "br"]);
const VOID_TAGS = new Set(["br"]);

const TAG_RE = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^<>]*?)?)\s*(\/?)>/g;
const ATTR_RE = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("[^"]*"|'[^']*')/g;

export type HtmlElementNode = { tag: string; href?: string; children: HtmlNode[] };
export type HtmlNode = string | HtmlElementNode;

/** Parses `value`; returns `null` when it uses anything outside the allowlist. */
export function parseAllowedHtml(value: string): HtmlNode[] | null {
  const root: HtmlNode[] = [];
  const stack: HtmlElementNode[] = [];

  const pushText = (text: string) => {
    if (!text) return;
    const target = stack.length ? stack[stack.length - 1].children : root;
    target.push(text);
  };

  let lastEnd = 0;
  TAG_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = TAG_RE.exec(value))) {
    const gap = value.slice(lastEnd, match.index);
    if (gap.includes("<") || gap.includes(">")) return null;
    pushText(gap);
    lastEnd = TAG_RE.lastIndex;

    const closing = match[1] === "/";
    const name = match[2].toLowerCase();
    const attrsRaw = (match[3] || "").trim();
    const selfClose = match[4] === "/";

    if (!ALLOWED_TAGS.has(name)) return null;

    if (closing) {
      if (attrsRaw || stack.length === 0 || stack[stack.length - 1].tag !== name) return null;
      const node = stack.pop()!;
      (stack.length ? stack[stack.length - 1].children : root).push(node);
      continue;
    }

    let href: string | undefined;
    if (name === "a") {
      const attrs: Record<string, string> = {};
      ATTR_RE.lastIndex = 0;
      let attrMatch: RegExpExecArray | null;
      while ((attrMatch = ATTR_RE.exec(attrsRaw))) {
        attrs[attrMatch[1].toLowerCase()] = attrMatch[2].slice(1, -1);
      }
      const names = Object.keys(attrs);
      if (names.some((n) => n !== "href") || !("href" in attrs)) return null;
      href = attrs.href;
    } else if (attrsRaw) {
      return null;
    }

    if (VOID_TAGS.has(name) || selfClose) {
      const node: HtmlElementNode = { tag: name, href, children: [] };
      (stack.length ? stack[stack.length - 1].children : root).push(node);
    } else {
      stack.push({ tag: name, href, children: [] });
    }
  }

  const tail = value.slice(lastEnd);
  if (tail.includes("<") || tail.includes(">")) return null;
  pushText(tail);

  return stack.length === 0 ? root : null;
}

export function isHtmlAllowed(value: string): boolean {
  return value === "" || parseAllowedHtml(value) !== null;
}

/** `^[a-z0-9-]{3,60}$` — mirrors `admin_content.py:SLUG_RE`. */
export const SLUG_RE = /^[a-z0-9-]{3,60}$/;

/** Per-field length caps (chars) — mirrors `admin_content.py:FIELD_MAX_LEN`. */
export const FIELD_MAX_LEN = {
  title: 300,
  summary: 600,
  full_text: 4000,
  source_label: 200,
  name: 100,
} as const;
