import { Fragment, useRef, useState, type ElementType, type ReactNode } from "react";
import { Bold, Code2, CornerDownLeft, Eye, EyeOff, Italic, Link2, Underline } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { IconButton } from "../ui/Button";
import { isHtmlAllowed, parseAllowedHtml, type HtmlNode } from "./richtext";

/** The dense field skin shared by the content editor (13px, 36px controls). */
export const FIELD_INPUT =
  "w-full rounded-xl border border-border bg-surface px-2.5 py-2 text-[13px] text-text " +
  "placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

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
        <a key={key} href={node.href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
          {children}
        </a>
      );
    case "br":
      return <br key={key} />;
    default:
      return null;
  }
}

export type RichTextFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  maxLen: number;
  placeholder?: string;
  rows?: number;
  required?: boolean;
  /** Hides the markup buttons (short plain fields: a name, a source label). */
  toolbar?: boolean;
  /** Inline error already resolved to a translated string (live check or server response). */
  errorText?: string;
};

/**
 * A textarea with the allowlist toolbar, a length counter and a preview that
 * renders through the same parser the backend enforces (`richtext.ts`) instead
 * of `dangerouslySetInnerHTML` — invalid markup shows a warning, never HTML.
 */
export default function RichTextField({
  label,
  value,
  onChange,
  maxLen,
  placeholder,
  rows = 4,
  required = false,
  toolbar = true,
  errorText,
}: RichTextFieldProps) {
  const t = useT();
  const ref = useRef<HTMLTextAreaElement>(null);
  // Edit / preview is a mode of this one field (not an overlay), so it stays
  // local: there is nothing for the back button to close.
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const preview = mode === "preview";

  const length = value.length;
  const over = length > maxLen;
  const htmlOk = isHtmlAllowed(value);

  const wrapSelection = (open: string, close: string, placeholderText: string) => {
    const el = ref.current;
    if (!el) return;
    const start = el.selectionStart ?? value.length;
    const end = el.selectionEnd ?? value.length;
    const selected = value.slice(start, end) || placeholderText;
    onChange(value.slice(0, start) + open + selected + close + value.slice(end));
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
    onChange(value.slice(0, pos) + text + value.slice(pos));
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

  const actions: { icon: ElementType; labelKey: TranslationKey; run: () => void }[] = [
    { icon: Bold, labelKey: "adminContent.toolbar.bold", run: () => wrapSelection("<b>", "</b>", t("adminContent.toolbar.sample")) },
    { icon: Italic, labelKey: "adminContent.toolbar.italic", run: () => wrapSelection("<i>", "</i>", t("adminContent.toolbar.sample")) },
    { icon: Underline, labelKey: "adminContent.toolbar.underline", run: () => wrapSelection("<u>", "</u>", t("adminContent.toolbar.sample")) },
    { icon: Code2, labelKey: "adminContent.toolbar.code", run: () => wrapSelection("<code>", "</code>", t("adminContent.toolbar.sample")) },
    { icon: Link2, labelKey: "adminContent.toolbar.link", run: insertLink },
    { icon: CornerDownLeft, labelKey: "adminContent.toolbar.br", run: () => insertAtCursor("<br>") },
  ];

  const parsed = preview ? parseAllowedHtml(value) : null;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate text-[11px] font-semibold text-muted">
          {label}
          {required && <span className="text-danger"> *</span>}
        </span>
        {toolbar && (
          <div role="toolbar" aria-label={t("adminContent.toolbar.aria")} className="flex shrink-0 items-center">
            {actions.map(({ icon, labelKey, run }) => (
              <IconButton
                key={labelKey}
                icon={icon}
                variant="ghost"
                ariaLabel={t(labelKey)}
                disabled={preview}
                onClick={run}
              />
            ))}
            <IconButton
              icon={preview ? EyeOff : Eye}
              variant={preview ? "secondary" : "ghost"}
              ariaLabel={t(preview ? "adminContent.toolbar.hidePreview" : "adminContent.toolbar.showPreview")}
              onClick={() => setMode(preview ? "edit" : "preview")}
            />
          </div>
        )}
      </div>

      {preview ? (
        <div
          className="whitespace-pre-wrap break-words rounded-xl border border-border bg-surfaceAlt px-2.5 py-2 text-[13px] text-text"
          style={{ minHeight: `${Math.max(rows, 2) * 1.4}rem` }}
        >
          {parsed ? parsed.map((node, i) => renderNode(node, i)) : <span className="text-danger">{t("adminContent.toolbar.invalidHtml")}</span>}
        </div>
      ) : (
        <textarea
          ref={ref}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          rows={rows}
          aria-label={label}
          aria-invalid={over || !htmlOk || Boolean(errorText)}
          className={`${FIELD_INPUT} resize-y font-mono`}
        />
      )}

      <div className="flex items-start justify-between gap-2 text-[11px]">
        <span className="min-w-0 text-danger">
          {errorText || (!htmlOk && value ? t("adminContent.toolbar.invalidHtml") : "")}
        </span>
        <span className={`shrink-0 tabular-nums ${over ? "font-semibold text-danger" : "text-muted"}`}>
          {length}/{maxLen}
        </span>
      </div>
    </div>
  );
}
