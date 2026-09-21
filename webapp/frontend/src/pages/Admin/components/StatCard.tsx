import type { ElementType, ReactNode } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type StatCardProps = {
  labelKey: TranslationKey;
  /** Already formatted (use `useLocale().formatNumber` / `formatMoney`). */
  value: ReactNode;
  /** Change vs. the previous period, in percent. Sign drives colour + arrow. */
  delta?: number | null;
  /** Small caption under the value. */
  hint?: ReactNode;
  icon?: ElementType;
  /** Rendered instead of the value while the source query is pending. */
  loading?: boolean;
  className?: string;
};

/** One KPI tile. The dashboard and every page header use this, nothing else. */
export default function StatCard({
  labelKey,
  value,
  delta,
  hint,
  icon: Icon,
  loading = false,
  className = "",
}: StatCardProps) {
  const t = useT();
  const hasDelta = typeof delta === "number" && Number.isFinite(delta) && delta !== 0;
  const up = (delta ?? 0) > 0;
  const deltaText = hasDelta ? `${up ? "+" : ""}${Math.round(delta! * 10) / 10}%` : "";

  return (
    <div className={`card p-3.5 ${className}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 text-[11px] font-medium uppercase tracking-wide text-muted">
          {t(labelKey)}
        </p>
        {Icon && (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Icon size={13} aria-hidden="true" />
          </span>
        )}
      </div>

      {loading ? (
        <div className="mt-2 h-6 w-20 animate-pulse rounded-lg bg-surfaceAlt" />
      ) : (
        <p className="mt-1.5 font-display text-xl font-extrabold leading-tight text-text">{value}</p>
      )}

      <div className="mt-1 flex items-center gap-2">
        {hasDelta && (
          <span
            className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${
              up ? "text-success" : "text-danger"
            }`}
            aria-label={t(up ? "admin.stat.deltaUp" : "admin.stat.deltaDown", {
              value: deltaText,
            })}
          >
            {up ? <TrendingUp size={12} aria-hidden="true" /> : <TrendingDown size={12} aria-hidden="true" />}
            {deltaText}
          </span>
        )}
        {hint && <span className="min-w-0 truncate text-[11px] text-muted">{hint}</span>}
      </div>
    </div>
  );
}
