import { ChevronRight } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type JsonDetailsProps = {
  data: unknown;
  labelKey: TranslationKey;
  className?: string;
};

function isEmpty(data: unknown): boolean {
  if (data === null || data === undefined) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === "object") return Object.keys(data as object).length === 0;
  return false;
}

/**
 * A native `<details>`/`<summary>` JSON viewer — used for audit payloads,
 * error contexts and the scheduler's raw `next_slots`. Native disclosure
 * markup gets keyboard + screen-reader support for free.
 */
export default function JsonDetails({ data, labelKey, className = "" }: JsonDetailsProps) {
  const t = useT();

  if (isEmpty(data)) return <span className="text-xs text-muted">—</span>;

  return (
    <details className={`group ${className}`}>
      <summary className="tap-target inline-flex cursor-pointer list-none items-center gap-1 text-xs font-semibold text-primary marker:content-none focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40">
        <ChevronRight
          size={12}
          aria-hidden="true"
          className="shrink-0 transition-transform group-open:rotate-90"
        />
        {t(labelKey)}
      </summary>
      <pre className="mt-1.5 max-h-64 max-w-xs overflow-auto whitespace-pre-wrap break-all rounded-lg bg-surfaceAlt p-2 text-left text-[11px] leading-snug text-text">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  );
}
