import type { ReactNode } from "react";
import { Search, X } from "lucide-react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

const CONTROL =
  "w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

export type FilterBarProps = {
  children: ReactNode;
  /** Shown as a "clear all" button when provided. */
  onReset?: () => void;
  className?: string;
};

export type FilterSearchProps = {
  value: string;
  onChange: (value: string) => void;
  placeholderKey?: TranslationKey;
  className?: string;
};

export type FilterOption = { value: string; labelKey: TranslationKey };

export type FilterSelectProps = {
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  /** Prepended as an "all" option with an empty value. */
  allKey?: TranslationKey;
  labelKey?: TranslationKey;
  className?: string;
};

export type FilterToggleProps = {
  value: boolean;
  onChange: (value: boolean) => void;
  labelKey: TranslationKey;
  className?: string;
};

export type FilterDateRangeProps = {
  /** `YYYY-MM-DD` (empty string = unset), matching the API `from`/`to` params. */
  from: string;
  to: string;
  onChange: (range: { from: string; to: string }) => void;
  className?: string;
};

function FilterSearch({ value, onChange, placeholderKey = "admin.filter.searchPlaceholder", className = "" }: FilterSearchProps) {
  const t = useT();
  return (
    <div className={`relative min-w-0 flex-1 ${className}`}>
      <Search
        size={14}
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
      />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={t(placeholderKey)}
        aria-label={t(placeholderKey)}
        className={`${CONTROL} pl-8`}
      />
    </div>
  );
}

function FilterSelect({ value, onChange, options, allKey, labelKey, className = "" }: FilterSelectProps) {
  const t = useT();
  return (
    <label className={`min-w-0 ${className}`}>
      {labelKey && <span className="sr-only">{t(labelKey)}</span>}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={labelKey ? t(labelKey) : undefined}
        className={CONTROL}
      >
        {allKey && <option value="">{t(allKey)}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {t(option.labelKey)}
          </option>
        ))}
      </select>
    </label>
  );
}

function FilterToggle({ value, onChange, labelKey, className = "" }: FilterToggleProps) {
  const t = useT();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      onClick={() => onChange(!value)}
      className={`tap-target shrink-0 rounded-xl border px-3 py-2 text-xs font-semibold transition-colors ${
        value ? "border-primary bg-primary/10 text-primary" : "border-border bg-surface text-muted"
      } ${className}`}
    >
      {t(labelKey)}
    </button>
  );
}

function FilterDateRange({ from, to, onChange, className = "" }: FilterDateRangeProps) {
  const t = useT();
  return (
    <div className={`flex min-w-0 items-center gap-1.5 ${className}`}>
      <input
        type="date"
        value={from}
        max={to || undefined}
        onChange={(event) => onChange({ from: event.target.value, to })}
        aria-label={t("admin.filter.from")}
        className={CONTROL}
      />
      <span aria-hidden="true" className="text-xs text-muted">
        —
      </span>
      <input
        type="date"
        value={to}
        min={from || undefined}
        onChange={(event) => onChange({ from, to: event.target.value })}
        aria-label={t("admin.filter.to")}
        className={CONTROL}
      />
    </div>
  );
}

/**
 * Composable filter row. Children are laid out in a wrapping flex row so a
 * page picks only what it needs:
 *
 *   <FilterBar onReset={reset}>
 *     <FilterBar.Search value={q} onChange={setQ} />
 *     <FilterBar.Select value={pro} onChange={setPro} options={PRO} allKey="admin.filter.all" />
 *     <FilterBar.Toggle value={banned} onChange={setBanned} labelKey="adminUsers.filter.banned" />
 *     <FilterBar.DateRange from={from} to={to} onChange={setRange} />
 *   </FilterBar>
 */
export default function FilterBar({ children, onReset, className = "" }: FilterBarProps) {
  const t = useT();
  return (
    <div
      role="search"
      aria-label={t("admin.filter.aria")}
      className={`flex flex-wrap items-center gap-2 ${className}`}
    >
      {children}
      {onReset && (
        <button
          type="button"
          onClick={onReset}
          className="tap-target inline-flex shrink-0 items-center gap-1 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-semibold text-muted"
        >
          <X size={12} aria-hidden="true" />
          {t("admin.filter.reset")}
        </button>
      )}
    </div>
  );
}

FilterBar.Search = FilterSearch;
FilterBar.Select = FilterSelect;
FilterBar.Toggle = FilterToggle;
FilterBar.DateRange = FilterDateRange;
