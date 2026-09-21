import { useId, useRef } from "react";
import { Bold, Code, Italic, Link2, Underline } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { escapeHtml, isAllowedLink, type HtmlCheck } from "./telegramHtml";

export type HtmlEditorProps = {
  value: string;
  onChange: (value: string) => void;
  labelKey: TranslationKey;
  limit: number;
  check: HtmlCheck;
  /** Rendered under the preview (e.g. the inline buttons mock-up). */
  previewFooter?: React.ReactNode;
};

type Wrap = { open: string; close: string };

/**
 * A plain textarea over Telegram's HTML source plus a small toolbar that wraps
 * the selection. Deliberately *not* a contentEditable WYSIWYG: the server
 * validates the raw HTML, so the admin should see exactly what it will get —
 * and a textarea keeps the Telegram in-app keyboard predictable.
 */
export default function HtmlEditor({
  value,
  onChange,
  labelKey,
  limit,
  check,
  previewFooter,
}: HtmlEditorProps) {
  const t = useT();
  const { formatNumber } = useLocale();
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const textareaId = useId();
  const counterId = useId();

  const over = Math.max(0, check.length - limit);

  const wrapSelection = ({ open, close }: Wrap) => {
    const area = areaRef.current;
    if (!area) return;
    const start = area.selectionStart ?? value.length;
    const end = area.selectionEnd ?? value.length;
    const next = `${value.slice(0, start)}${open}${value.slice(start, end)}${close}${value.slice(end)}`;
    onChange(next);
    // Put the caret inside the new tags on the next frame, after React re-renders.
    requestAnimationFrame(() => {
      area.focus();
      const caret = start + open.length;
      area.setSelectionRange(caret, caret + (end - start));
    });
  };

  const insertLink = () => {
    const href = window.prompt(t("adminBroadcasts.toolbar.linkPrompt"), "https://");
    if (!href || !isAllowedLink(href)) return;
    const normalized = /^(https?:|tg:)/i.test(href.trim()) ? href.trim() : `https://${href.trim()}`;
    wrapSelection({ open: `<a href="${escapeHtml(normalized)}">`, close: "</a>" });
  };

  const tools: { key: TranslationKey; icon: typeof Bold; onClick: () => void }[] = [
    { key: "adminBroadcasts.toolbar.bold", icon: Bold, onClick: () => wrapSelection({ open: "<b>", close: "</b>" }) },
    { key: "adminBroadcasts.toolbar.italic", icon: Italic, onClick: () => wrapSelection({ open: "<i>", close: "</i>" }) },
    { key: "adminBroadcasts.toolbar.underline", icon: Underline, onClick: () => wrapSelection({ open: "<u>", close: "</u>" }) },
    { key: "adminBroadcasts.toolbar.link", icon: Link2, onClick: insertLink },
    { key: "adminBroadcasts.toolbar.code", icon: Code, onClick: () => wrapSelection({ open: "<code>", close: "</code>" }) },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor={textareaId} className="text-xs font-semibold text-muted">
          {t(labelKey)}
        </label>
        <span
          id={counterId}
          aria-live="polite"
          className={`text-xs tabular-nums ${over > 0 ? "font-semibold text-danger" : "text-muted"}`}
        >
          {t("adminBroadcasts.composer.counter", {
            count: formatNumber(check.length),
            max: formatNumber(limit),
          })}
        </span>
      </div>

      <div className="rounded-xl border border-border bg-surface">
        <div className="flex flex-wrap items-center gap-1 border-b border-border px-2 py-1.5" role="toolbar" aria-label={t(labelKey)}>
          {tools.map(({ key, icon: Icon, onClick }) => (
            <button
              key={key}
              type="button"
              onClick={onClick}
              title={t(key)}
              aria-label={t(key)}
              className="rounded-lg p-1.5 text-muted transition-colors hover:bg-surfaceAlt hover:text-text focus:outline-none focus:ring-2 focus:ring-primary/40"
            >
              <Icon size={15} aria-hidden="true" />
            </button>
          ))}
        </div>

        <textarea
          id={textareaId}
          ref={areaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          rows={7}
          spellCheck={false}
          aria-describedby={counterId}
          aria-invalid={over > 0 || check.reason !== null}
          placeholder={t("adminBroadcasts.composer.textPlaceholder")}
          className="w-full resize-y rounded-b-xl bg-transparent px-3 py-2.5 font-mono text-sm text-text placeholder:text-muted/70 focus:outline-none"
        />
      </div>

      {over > 0 && (
        <p role="alert" className="text-xs text-danger">
          {t("adminBroadcasts.composer.counterOver", { over: formatNumber(over) })}
        </p>
      )}
      {check.reason && (
        <p role="alert" className="text-xs text-danger">
          {t("adminBroadcasts.error.badHtml", { reason: check.reason })}
        </p>
      )}

      <div>
        <p className="mb-1.5 text-xs font-semibold text-muted">{t("adminBroadcasts.composer.preview")}</p>
        <div className="rounded-xl border border-border bg-surfaceAlt p-3">
          {check.html ? (
            // Safe: `check.html` was rebuilt from the Telegram allowlist in
            // telegramHtml.ts — every text node is escaped and no attribute
            // other than a validated `href` / `class="tg-spoiler"` survives.
            <div
              className="whitespace-pre-wrap break-words text-sm text-text [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-surface [&_code]:px-1 [&_code]:font-mono"
              dangerouslySetInnerHTML={{ __html: check.html }}
            />
          ) : (
            <p className="text-sm text-muted">{t("adminBroadcasts.composer.previewEmpty")}</p>
          )}
          {previewFooter}
        </div>
      </div>
    </div>
  );
}
