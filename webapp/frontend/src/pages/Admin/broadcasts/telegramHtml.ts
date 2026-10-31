/**
 * Telegram's HTML subset, mirrored on the client.
 *
 * The authority is `webapp/routers/admin_broadcasts.py` (`ALLOWED_TAGS`,
 * `_TelegramHTMLValidator`, `validate_buttons`): the same allowlist, the same
 * link schemes, the same 4096/1024 visible-character limits. Doing it here
 * twice is deliberate — the composer must be able to say "this will be
 * rejected" before an admin queues 50 000 recipients, and the preview panel
 * must never render anything the allowlist does not contain.
 *
 * What is sent to the API is the *sanitized* string, not the raw textarea
 * contents: the browser's parser closes stray tags for us, so what the server
 * validates is always well formed.
 */

/** Exactly `ALLOWED_TAGS` in the router. */
export const ALLOWED_TAGS = new Set([
  "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
  "a", "code", "pre", "blockquote", "span", "tg-spoiler", "br",
]);

const VOID_TAGS = new Set(["br"]);
const ALLOWED_SCHEMES = new Set(["http:", "https:", "tg:"]);

export const MAX_TEXT_LENGTH = 4096;
export const MAX_CAPTION_LENGTH = 1024;
export const MAX_BUTTONS = 6;

export type HtmlCheck = {
  /** Allowlisted, well-formed HTML — this is what gets sent. */
  html: string;
  /** Visible characters, i.e. what Telegram counts against the limit. */
  length: number;
  /** First problem found, as a machine reason (`tag_not_allowed:marquee`). */
  reason: string | null;
};

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** `a href` / inline-button URL rule: http(s) or tg, plus bare `t.me/...`. */
export function isAllowedLink(href: string): boolean {
  const value = (href || "").trim();
  if (!value) return false;
  const candidate = /^(https?:|tg:)/i.test(value) ? value : `https://${value}`;
  try {
    const url = new URL(candidate);
    if (!ALLOWED_SCHEMES.has(url.protocol.toLowerCase())) return false;
    if (url.protocol.toLowerCase() === "tg:") return true;
    return Boolean(url.hostname);
  } catch {
    return false;
  }
}

/** Inline-button URLs are stricter than `a href`: http(s) or t.me only. */
export function isAllowedButtonUrl(url: string): boolean {
  const value = (url || "").trim();
  if (!value) return false;
  if (/^https?:\/\//i.test(value)) return true;
  return /^(https?:\/\/)?t\.me\//i.test(value);
}

function serialize(node: Node, out: string[], problem: { reason: string | null }): void {
  if (node.nodeType === Node.TEXT_NODE) {
    out.push(escapeHtml(node.nodeValue ?? ""));
    return;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return;

  const element = node as Element;
  const tag = element.localName.toLowerCase();

  const children = () => {
    for (const child of Array.from(element.childNodes)) serialize(child, out, problem);
  };

  if (!ALLOWED_TAGS.has(tag)) {
    if (!problem.reason) problem.reason = `tag_not_allowed:${tag}`;
    children();
    return;
  }

  if (VOID_TAGS.has(tag)) {
    out.push("<br>");
    return;
  }

  if (tag === "a") {
    const href = (element.getAttribute("href") ?? "").trim();
    if (!isAllowedLink(href)) {
      if (!problem.reason) problem.reason = "bad_link";
      children();
      return;
    }
    const normalized = /^(https?:|tg:)/i.test(href) ? href : `https://${href}`;
    out.push(`<a href="${escapeHtml(normalized)}">`);
    children();
    out.push("</a>");
    return;
  }

  if (tag === "span") {
    if ((element.getAttribute("class") ?? "").trim() !== "tg-spoiler") {
      if (!problem.reason) problem.reason = "span_requires_tg_spoiler";
      children();
      return;
    }
    out.push('<span class="tg-spoiler">');
    children();
    out.push("</span>");
    return;
  }

  // Every other allowed tag carries no attributes at all.
  if (element.attributes.length > 0 && !problem.reason) {
    problem.reason = `attributes_not_allowed:${tag}`;
  }
  out.push(`<${tag}>`);
  children();
  out.push(`</${tag}>`);
}

/**
 * Parse → allowlist → re-serialize, plus the visible length and the first
 * rule the input broke (`null` when it is clean).
 */
export function checkTelegramHtml(raw: string): HtmlCheck {
  const source = raw ?? "";
  if (!source.trim()) return { html: "", length: 0, reason: null };

  const doc = new DOMParser().parseFromString(`<body>${source}</body>`, "text/html");
  const problem: { reason: string | null } = { reason: null };
  const out: string[] = [];
  for (const child of Array.from(doc.body.childNodes)) serialize(child, out, problem);

  const html = out.join("");
  // `<br>` counts as a newline for Telegram; textContent already ignores tags.
  const length = doc.body.textContent?.length ?? 0;
  return { html, length, reason: problem.reason };
}

/** The character budget for a broadcast kind (caption vs. message body). */
export function limitForKind(kind: string): number {
  return kind === "text" ? MAX_TEXT_LENGTH : MAX_CAPTION_LENGTH;
}
