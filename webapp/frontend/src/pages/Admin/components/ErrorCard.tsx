import { AlertTriangle } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import parseApiError from "../../../lib/parseApiError";

export type ErrorCardProps = {
  error: unknown;
  onRetry?: () => void;
  className?: string;
};

/**
 * Renders an API failure as a translated message.
 *
 * The old page printed `e.response.data.detail` straight into the DOM, which
 * became "[object Object]" as soon as the backend started sending
 * `{code, ...params}` (see CONTRACT.md).
 */
export default function ErrorCard({ error, onRetry, className = "" }: ErrorCardProps) {
  const t = useT();
  const parsed = parseApiError(error);
  const key = `error.${parsed.code}` as TranslationKey;
  let text = t(key, parsed.params as Record<string, string | number>);
  if (text === key) text = parsed.message || t("error.UNKNOWN");

  return (
    <div
      role="alert"
      className={`rounded-2xl border border-danger/40 bg-danger/10 p-4 text-sm text-danger ${className}`}
    >
      <p className="flex items-start gap-2">
        <AlertTriangle size={16} className="mt-0.5 shrink-0" />
        <span className="min-w-0 flex-1">{text}</span>
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="tap-target mt-3 rounded-xl border border-danger/40 px-3 py-1.5 text-xs font-semibold text-danger"
        >
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}
