import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";

export type BadgeTone = "success" | "danger" | "muted" | "warning";

const TONE: Record<BadgeTone, string> = {
  success: "bg-success/10 text-success",
  danger: "bg-danger/10 text-danger",
  warning: "bg-warning/10 text-warning",
  muted: "bg-surfaceAlt text-muted",
};

/** A small pill used by both the history table and the schedule/job states. */
export default function StatusBadge({ tone, labelKey }: { tone: BadgeTone; labelKey: TranslationKey }) {
  const t = useT();
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${TONE[tone]}`}
    >
      {t(labelKey)}
    </span>
  );
}
