import type { BroadcastButton } from "../../../api/adminTypes";
import { useT } from "../../../i18n/useT";
import { renderSafeHtml, TELEGRAM_HTML } from "../../../lib/safeHtml";

export type MessagePreviewProps = {
  /** Already sanitized by `checkTelegramHtml` — never raw admin input. */
  html: string;
  buttons?: BroadcastButton[];
};

/**
 * How the message will look in Telegram: the sanitized HTML plus the inline
 * keyboard mock-up. Not a card — it is the bubble inside its own section.
 */
export default function MessagePreview({ html, buttons = [] }: MessagePreviewProps) {
  const t = useT();
  const rows = buttons.filter((row) => row.text.trim() || row.url.trim());

  return (
    <div className="rounded-xl bg-surfaceAlt p-3">
      {html ? (
        // Rendered as React nodes through the Telegram allowlist (lib/safeHtml.ts),
        // on top of the sanitizing in telegramHtml.ts — never as raw HTML.
        <div className="whitespace-pre-wrap break-words text-[13px] text-text [&_a]:text-primary [&_a]:underline [&_code]:rounded [&_code]:bg-surface [&_code]:px-1 [&_code]:font-mono">
          {renderSafeHtml(html, TELEGRAM_HTML)}
        </div>
      ) : (
        <p className="text-[13px] text-muted">{t("adminBroadcasts.composer.previewEmpty")}</p>
      )}

      {rows.length > 0 && (
        <div className="mt-2 space-y-1">
          {rows.map((row, index) => (
            <div
              key={index}
              className="truncate rounded-lg bg-surface px-2.5 py-1.5 text-center text-[13px] font-medium text-primary"
            >
              {row.text || row.url}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
