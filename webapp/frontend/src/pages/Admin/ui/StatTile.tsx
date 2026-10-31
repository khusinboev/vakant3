import type { ReactNode } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type StatTileProps = {
  labelKey?: TranslationKey;
  label?: string;
  /** Already formatted (`useLocale().formatNumber` / `formatMoney`). */
  value: ReactNode;
  /** Change vs. the previous period in percent; sign drives colour + arrow. */
  delta?: number | null;
  hint?: ReactNode;
  loading?: boolean;
  to?: string;
  className?: string;
};

/** 64px KPI tile — four of them fit in a 2×2 grid under 140px (spec §6). */
export default function StatTile({
  labelKey,
  label,
  value,
  delta,
  hint,
  loading = false,
  to,
  className = "",
}: StatTileProps) {
  const t = useT();
  const hasDelta = typeof delta === "number" && Number.isFinite(delta) && delta !== 0;
  const up = (delta ?? 0) > 0;
  const deltaText = hasDelta ? `${up ? "+" : ""}${Math.round(delta! * 10) / 10}%` : "";

  const body = (
    <>
      <p className="truncate text-[11px] font-medium uppercase tracking-wide text-muted">
        {labelKey ? t(labelKey) : label}
      </p>
      {loading ? (
        <div className="mt-1 h-5 w-16 animate-pulse rounded-lg bg-surfaceAlt" />
      ) : (
        <p className="mt-0.5 truncate text-[18px] font-bold leading-tight tabular-nums text-text">
          {value}
        </p>
      )}
      {(hasDelta || hint) && (
        <p className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-muted">
          {hasDelta && (
            <span
              className={`inline-flex items-center gap-0.5 font-semibold ${
                up ? "text-success" : "text-danger"
              }`}
              aria-label={t(up ? "admin.stat.deltaUp" : "admin.stat.deltaDown", {
                value: deltaText,
              })}
            >
              {up ? (
                <TrendingUp size={11} aria-hidden="true" />
              ) : (
                <TrendingDown size={11} aria-hidden="true" />
              )}
              {deltaText}
            </span>
          )}
          {hint && <span className="min-w-0 truncate">{hint}</span>}
        </p>
      )}
    </>
  );

  const classes = `flex min-h-[64px] flex-col justify-center rounded-xl border border-border bg-surface px-3 py-2 ${className}`;

  return to ? (
    <Link to={to} className={`${classes} hover:bg-surfaceAlt`}>
      {body}
    </Link>
  ) : (
    <div className={classes}>{body}</div>
  );
}
