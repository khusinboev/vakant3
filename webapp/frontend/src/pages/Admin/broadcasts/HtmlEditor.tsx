import { useId, useRef } from "react";
import { Bold, Code, Italic, Link2, Underline } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import { IconButton } from "../ui";
import { escapeHtml, isAllowedLink, type HtmlCheck } from "./telegramHtml";

export type HtmlEditorProps = {
  value: string;
  onChange: (value: string) => void;
  labelKey: TranslationKey;
  limit: number;
  check: HtmlCheck;
};

type Wrap = { open: string; close: string };

/**
 * A plain textarea over Telegram's HTML source plus five 32px toolbar icons
 * that wrap the selection. Deliberately *not* a contentEditable WYSIWYG: the
 * server validates the raw HTML, so the admin should see exactly what it will
 * get — and a textarea keeps the Telegram in-app keyboard predictable.
 */
export default function HtmlEditor({ value, onChange, labelKey, limit, check }: HtmlEditorProps) {
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
    <div className="space-y-2">
      <div className="flex items-center gap-0.5" role="toolbar" aria-label={t(labelKey)}>
        {tools.map(({ key, icon, onClick }) => (
          <IconButton key={key} icon={icon} variant="ghost" ariaLabel={t(key)} onClick={onClick} />
        ))}
        <span
          id={counterId}
          aria-live="polite"
          className={`ml-auto shrink-0 pr-1 text-[11px] tabular-nums ${
            over > 0 ? "font-semibold text-danger" : "text-muted"
          }`}
        >
          {t("adminBroadcasts.composer.counter", {
            count: formatNumber(check.length),
            max: formatNumber(limit),
          })}
        </span>
      </div>

      <textarea
        id={textareaId}
        ref={areaRef}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        rows={6}
        spellCheck={false}
        aria-label={t(labelKey)}
        aria-describedby={counterId}
        aria-invalid={over > 0 || check.reason !== null}
        placeholder={t("adminBroadcasts.composer.textPlaceholder")}
        className="w-full resize-y rounded-xl border border-border bg-surface px-2.5 py-2 font-mono text-[13px] text-text placeholder:text-muted/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40"
      />

      {over > 0 && (
        <p role="alert" className="text-[11px] text-danger">
          {t("adminBroadcasts.composer.counterOver", { over: formatNumber(over) })}
        </p>
      )}
      {check.reason && (
        <p role="alert" className="text-[11px] text-danger">
          {t("adminBroadcasts.error.badHtml", { reason: check.reason })}
        </p>
      )}
    </div>
  );
}
