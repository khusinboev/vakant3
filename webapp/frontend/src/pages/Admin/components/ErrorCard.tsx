import { AlertTriangle } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import parseApiError from "../../../lib/parseApiError";
import Button from "../ui/Button";

export type ErrorCardProps = {
  error: unknown;
  onRetry?: () => void;
  className?: string;
};

/** An API failure as a translated message, in the admin density scale. */
export default function ErrorCard({ error, onRetry, className = "" }: ErrorCardProps) {
  const t = useT();
  const parsed = parseApiError(error);
  const key = `error.${parsed.code}` as TranslationKey;
  let text = t(key, parsed.params as Record<string, string | number>);
  if (text === key) text = parsed.message || t("error.UNKNOWN");

  return (
    <div
      role="alert"
      className={`rounded-xl border border-danger/40 bg-danger/10 p-3 text-[13px] text-danger ${className}`}
    >
      <p className="flex items-start gap-2">
        <AlertTriangle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span className="min-w-0 flex-1">{text}</span>
      </p>
      {onRetry && (
        <Button
          size="sm"
          variant="secondary"
          labelKey="common.retry"
          onClick={onRetry}
          className="mt-2 border-danger/40 bg-transparent text-danger"
        />
      )}
    </div>
  );
}
