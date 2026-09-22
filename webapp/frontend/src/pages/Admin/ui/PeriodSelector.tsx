/* eslint-disable react-refresh/only-export-components -- the kit ships helpers next to their component. */
import type { TranslationKey } from "../../../i18n";
import { SegmentedControl } from "./Tabs";

export type PeriodValue = "7" | "30" | "90" | "365";

export const PERIOD_LABEL_KEY: Record<PeriodValue, TranslationKey> = {
  "7": "admin.period.7",
  "30": "admin.period.30",
  "90": "admin.period.90",
  "365": "admin.period.365",
};

export type PeriodSelectorProps = {
  value: PeriodValue;
  onChange: (value: PeriodValue) => void;
  /** Which presets to show. Default 7 / 30 / 90. */
  periods?: PeriodValue[];
  full?: boolean;
  className?: string;
};

/** The one period switch (analytics + finance used to have one each). */
export default function PeriodSelector({
  value,
  onChange,
  periods = ["7", "30", "90"],
  full = false,
  className = "",
}: PeriodSelectorProps) {
  return (
    <SegmentedControl<PeriodValue>
      options={periods.map((period) => ({ value: period, labelKey: PERIOD_LABEL_KEY[period] }))}
      value={value}
      onChange={onChange}
      ariaLabelKey="admin.period.aria"
      full={full}
      className={className}
    />
  );
}

/** `"30"` -> `30`, for the `?days=` query parameter. */
export function periodDays(value: PeriodValue): number {
  return Number(value);
}
