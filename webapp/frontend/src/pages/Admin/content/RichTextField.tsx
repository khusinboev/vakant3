import { Fragment, useRef, useState, type ReactNode } from "react";
import { Bold, Code2, CornerDownLeft, Eye, EyeOff, Italic, Link2, Underline } from "lucide-react";

import { INPUT_CLS } from "../../../components/ui/Field";
import { useT } from "../../../i18n/useT";
import { isHtmlAllowed, parseAllowedHtml, type HtmlNode } from "./richtext";

function renderNode(node: HtmlNode, key: number): ReactNode {
  if (typeof node === "string") return <Fragment key={key}>{node}</Fragment>;
  const children = node.children.map((child, i) => renderNode(child, i));
  switch (node.tag) {
    case "b":
      return <b key={key}>{children}</b>;
    case "i":
      return <i key={key}>{children}</i>;
    case "u":
      return <u key={key}>{children}</u>;
    case "code":
      return (
        <code key={key} className="rounded bg-surface px-1 py-0.5 text-[0.85em]">
          {children}
        </code>
      );
    case "a":
      return (
        <a
          key={key}
          href={node.href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary underline"
        >
          {children}
        </a>
      );
    case "br":
      return <br key={key} />;
    default:
      return null;
  }
}

function renderHtmlNodes(nodes: HtmlNode[]): ReactNode {
  return nodes.map((node, i) => renderNode(node, i));
}

export type RichTextFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  maxLen: number;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  required?: boolean;
  /** Inline error already resolved to a translated string (from a live check or a server response). */
  errorText?: string;
};

/**
 * A tri-state textarea: edit mode with a small allowlist toolbar, a live
 * length counter, and a "preview" mode that renders the value through the
 * same allowlist the backend enforces (`richtext.ts`) instead of
 * `dangerouslySetInnerHTML`.
 */
export default function RichTextField({
  label,
  value,
  onChange,
  maxLen,
  placeholder,
  rows = 4,
  disabled = false,
  required = false,
  errorText,
}: RichTextFieldProps) {
  const t = useT();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [preview, setPreview] = useState(false);

  const length = value.length;
  const over = length > maxLen;
  const htmlOk = isHtmlAllowed(value);

  const wrapSelection = (open: string, close: string, placeholderText: string) => {
    const el = ref.current;
    if (!el) return;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const selected = value.slice(start, end) || placeholderText;
    const next = value.slice(0, start) + open + selected + close + value.slice(end);
    onChange(next);
    const cursor = start + open.length + selected.length + close.length;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(cursor, cursor);
    });
  };

  const insertAtCursor = (text: string) => {
    const el = ref.current;
    if (!el) return;
    const pos = el.selectionStart ?? value.length;
    const next = value.slice(0, pos) + text + value.slice(pos);
    onChange(next);
    const cursor = pos + text.length;
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(cursor, cursor);
    });
  };

  const insertLink = () => {
    const href = window.prompt(t("adminContent.toolbar.linkPrompt"), "https://");
    if (!href) return;
    wrapSelection(`<a href="${href}">`, "</a>", t("adminContent.toolbar.linkSample"));
  };

  const toolbarBtn =
    "tap-target rounded-lg p-1.5 text-muted transition-colors hover:bg-surfaceAlt hover:text-text disabled:pointer-events-none disabled:opacity-40";

  const parsed = preview ? parseAllowedHtml(value) : null;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-baseline gap-1 text-xs font-semibold text-muted">
          {label}
          {required && <span className="text-danger">*</span>}
        </label>
        <div role="toolbar" aria-label={t("adminContent.toolbar.aria")} className="flex items-center gap-0.5">
          <button
            type="button"
            disabled={disabled || preview}
            onClick={() => wrapSelection("<b>", "</b>", t("adminContent.toolbar.sample"))}
            aria-label={t("adminContent.toolbar.bold")}
            title={t("adminContent.toolbar.bold")}
            className={toolbarBtn}
          >
            <Bold size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            disabled={disabled || preview}
            onClick={() => wrapSelection("<i>", "</i>", t("adminContent.toolbar.sample"))}
            aria-label={t("adminContent.toolbar.italic")}
            title={t("adminContent.toolbar.italic")}
            className={toolbarBtn}
          >
            <Italic size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            disabled={disabled || preview}
            onClick={() => wrapSelection("<u>", "</u>", t("adminContent.toolbar.sample"))}
            aria-label={t("adminContent.toolbar.underline")}
            title={t("adminContent.toolbar.underline")}
            className={toolbarBtn}
          >
            <Underline size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            disabled={disabled || preview}
            onClick={() => wrapSelection("<code>", "</code>", t("adminContent.toolbar.sample"))}
            aria-label={t("adminContent.toolbar.code")}
            title={t("adminContent.toolbar.code")}
            className={toolbarBtn}
          >
            <Code2 size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            disabled={disabled || preview}
            onClick={insertLink}
            aria-label={t("adminContent.toolbar.link")}
            title={t("adminContent.toolbar.link")}
            className={toolbarBtn}
          >
            <Link2 size={13} aria-hidden="true" />
          </button>
          <button
            type="button"
            disabled={disabled || preview}
            onClick={() => insertAtCursor("<br>")}
            aria-label={t("adminContent.toolbar.br")}
            title={t("adminContent.toolbar.br")}
            className={toolbarBtn}
          >
            <CornerDownLeft size={13} aria-hidden="true" />
          </button>
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-border" />
          <button
            type="button"
            onClick={() => setPreview((p) => !p)}
            aria-pressed={preview}
            aria-label={t(preview ? "adminContent.toolbar.hidePreview" : "adminContent.toolbar.showPreview")}
            title={t(preview ? "adminContent.toolbar.hidePreview" : "adminContent.toolbar.showPreview")}
            className={`${toolbarBtn} ${preview ? "bg-primary/10 !text-primary" : ""}`}
          >
            {preview ? <EyeOff size={13} aria-hidden="true" /> : <Eye size={13} aria-hidden="true" />}
          </button>
        </div>
      </div>

      {preview ? (
        <div
          className="min-h-[5rem] whitespace-pre-wrap break-words rounded-xl border border-border bg-surfaceAlt px-3 py-2.5 text-sm text-text"
          style={{ minHeight: `${rows * 1.5}rem` }}
        >
          {parsed ? (
            renderHtmlNodes(parsed)
          ) : (
            <span className="text-danger">{t("adminContent.toolbar.invalidHtml")}</span>
          )}
        </div>
      ) : (
        <textarea
          ref={ref}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          rows={rows}
          aria-invalid={over || !htmlOk || Boolean(errorText)}
          className={`${INPUT_CLS} resize-y font-mono text-[13px]`}
        />
      )}

      <div className="flex items-center justify-between gap-2 text-[11px]">
        <span className="text-danger">
          {errorText || (!htmlOk && value ? t("adminContent.toolbar.invalidHtml") : "")}
        </span>
        <span className={`shrink-0 ${over ? "font-semibold text-danger" : "text-muted"}`}>
          {length}/{maxLen}
        </span>
      </div>
    </div>
  );
}
