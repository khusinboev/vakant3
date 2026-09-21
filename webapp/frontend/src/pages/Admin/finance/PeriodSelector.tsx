import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export const FINANCE_PERIODS = [7, 30, 90, 365] as const;
export type FinancePeriod = (typeof FINANCE_PERIODS)[number];

const LABEL_KEY: Record<FinancePeriod, TranslationKey> = {
  7: "adminFinance.period.7d",
  30: "adminFinance.period.30d",
  90: "adminFinance.period.90d",
  365: "adminFinance.period.365d",
};

export type PeriodSelectorProps = {
  value: FinancePeriod;
  onChange: (value: FinancePeriod) => void;
  className?: string;
};

/** Segmented 7/30/90/365-day control driving the summary cards + chart. */
export default function PeriodSelector({ value, onChange, className = "" }: PeriodSelectorProps) {
  const t = useT();
  return (
    <div
      role="radiogroup"
      aria-label={t("adminFinance.period.aria")}
      className={`inline-flex shrink-0 gap-1 rounded-xl border border-border bg-surface p-1 ${className}`}
    >
      {FINANCE_PERIODS.map((period) => {
        const active = period === value;
        return (
          <button
            key={period}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(period)}
            className={`tap-target rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
              active ? "bg-primary text-primaryFg" : "text-muted hover:text-text"
            }`}
          >
            {t(LABEL_KEY[period])}
          </button>
        );
      })}
    </div>
  );
}
