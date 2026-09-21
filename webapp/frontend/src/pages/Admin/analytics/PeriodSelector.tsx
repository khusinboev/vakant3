import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type AnalyticsPeriod = 7 | 30 | 90;

const OPTIONS: { value: AnalyticsPeriod; labelKey: TranslationKey }[] = [
  { value: 7, labelKey: "admin.analytics2.period.7" },
  { value: 30, labelKey: "admin.analytics2.period.30" },
  { value: 90, labelKey: "admin.analytics2.period.90" },
];

export type PeriodSelectorProps = {
  value: AnalyticsPeriod;
  onChange: (value: AnalyticsPeriod) => void;
  className?: string;
};

/** 7 / 30 / 90 day segmented control driving the whole dashboard's window. */
export default function PeriodSelector({ value, onChange, className = "" }: PeriodSelectorProps) {
  const t = useT();
  return (
    <div
      role="radiogroup"
      aria-label={t("admin.analytics2.period.label")}
      className={`inline-flex shrink-0 rounded-xl border border-border bg-surface p-1 ${className}`}
    >
      {OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`tap-target rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              active ? "bg-primary text-primaryFg" : "text-muted hover:text-text"
            }`}
          >
            {t(option.labelKey)}
          </button>
        );
      })}
    </div>
  );
}
