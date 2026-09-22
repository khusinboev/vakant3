/* eslint-disable react-refresh/only-export-components -- the kit ships helpers next to their component. */
import type { ReactNode } from "react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useQueryState } from "../hooks/useQueryState";
import { Badge } from "./Chip";

export type TabDef<T extends string = string> = {
  id: T;
  labelKey?: TranslationKey;
  label?: string;
  /** Small count next to the label. */
  badge?: number;
};

export type TabsProps<T extends string = string> = {
  tabs: TabDef<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabelKey?: TranslationKey;
  className?: string;
};

/** 32px scrollable tab strip. Keep the selection in the URL (`useUrlTabs`). */
export function Tabs<T extends string = string>({
  tabs,
  value,
  onChange,
  ariaLabelKey = "admin.tabs.aria",
  className = "",
}: TabsProps<T>) {
  const t = useT();
  return (
    <div
      role="tablist"
      aria-label={t(ariaLabelKey)}
      className={`scrollbar-hide flex h-8 items-stretch gap-1 overflow-x-auto border-b border-border ${className}`}
    >
      {tabs.map((tab) => {
        const active = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={`inline-flex shrink-0 items-center gap-1 border-b-2 px-2.5 text-[13px] font-semibold transition-colors ${
              active
                ? "border-primary text-primary"
                : "border-transparent text-muted hover:text-text"
            }`}
          >
            {tab.labelKey ? t(tab.labelKey) : tab.label}
            {tab.badge !== undefined && tab.badge > 0 && <Badge count={tab.badge} />}
          </button>
        );
      })}
    </div>
  );
}

/**
 * A tab selection that lives in the URL, so back undoes it.
 *
 *   const [tab, setTab] = useUrlTabs("tab", "health");
 */
export function useUrlTabs<T extends string>(key: string, defaultTab: T): [T, (value: T) => void] {
  return useQueryState<T>(key, defaultTab);
}

export type SegmentedOption<T extends string = string> = {
  value: T;
  labelKey?: TranslationKey;
  label?: string;
};

export type SegmentedControlProps<T extends string = string> = {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  ariaLabelKey?: TranslationKey;
  ariaLabel?: string;
  full?: boolean;
  className?: string;
};

/** 28px segmented switch — language, period, small either/or choices. */
export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  ariaLabelKey,
  ariaLabel,
  full = false,
  className = "",
}: SegmentedControlProps<T>) {
  const t = useT();
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabelKey ? t(ariaLabelKey) : ariaLabel}
      className={`inline-flex h-7 items-stretch rounded-xl border border-border bg-surfaceAlt p-0.5 ${
        full ? "w-full" : ""
      } ${className}`}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`inline-flex min-w-0 flex-1 items-center justify-center rounded-lg px-2 text-[11px] font-semibold transition-colors ${
              active ? "bg-primary text-primaryFg" : "text-muted hover:text-text"
            }`}
          >
            <span className="truncate">{option.labelKey ? t(option.labelKey) : option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

export type TabPanelProps = { id: string; active: boolean; children: ReactNode };

/** Optional helper so a tab body carries the right aria wiring. */
export function TabPanel({ id, active, children }: TabPanelProps) {
  if (!active) return null;
  return (
    <div role="tabpanel" id={`panel-${id}`} className="pt-2">
      {children}
    </div>
  );
}

export default Tabs;
