import type { ReactNode } from "react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { TONE_CLASS, type Tone } from "./Chip";

export type KeyValueRow = {
  labelKey?: TranslationKey;
  label?: string;
  value: ReactNode;
  /** Colours the value (status-ish fields). */
  tone?: Tone;
  /** Drop the row entirely (optional fields). */
  hidden?: boolean;
};

export type KeyValueProps = {
  rows: KeyValueRow[];
  /** Wrap in a card border. Default `true`. */
  card?: boolean;
  className?: string;
};

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-text",
  primary: "text-primary",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  info: "text-primary",
};

/** The two-column detail list: label left, value right, 28px per row. */
export default function KeyValue({ rows, card = true, className = "" }: KeyValueProps) {
  const t = useT();
  const visible = rows.filter((row) => !row.hidden);
  if (visible.length === 0) return null;

  return (
    <dl
      className={`divide-y divide-border ${
        card ? "overflow-hidden rounded-xl border border-border bg-surface" : ""
      } ${className}`}
    >
      {visible.map((row, index) => (
        <div
          key={row.labelKey ?? row.label ?? index}
          className="flex min-h-[28px] items-center justify-between gap-3 px-3 py-1.5"
        >
          <dt className="shrink-0 text-[11px] text-muted">
            {row.labelKey ? t(row.labelKey) : row.label}
          </dt>
          <dd
            className={`min-w-0 truncate text-right text-[13px] font-medium tabular-nums ${
              TONE_TEXT[row.tone ?? "neutral"]
            }`}
          >
            {row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The tone -> border/background classes, for callers that build their own row. */
export { TONE_CLASS };
