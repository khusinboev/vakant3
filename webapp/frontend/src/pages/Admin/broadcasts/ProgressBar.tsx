import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";

export type ProgressBarProps = {
  sent: number;
  failed: number;
  blocked: number;
  total: number;
  /** Show the sent/failed/blocked legend under the bar. */
  detailed?: boolean;
};

/**
 * One stacked bar for a broadcast's counters: sent, failed and blocked out of
 * the materialized total. A draft has `total = 0`, so the bar stays empty
 * rather than dividing by zero.
 */
export default function ProgressBar({ sent, failed, blocked, total, detailed = false }: ProgressBarProps) {
  const t = useT();
  const { formatNumber } = useLocale();

  const safeTotal = Math.max(0, total);
  const pct = (value: number) => (safeTotal > 0 ? Math.min(100, (value / safeTotal) * 100) : 0);
  const done = sent + failed + blocked;

  return (
    <div className="min-w-[8rem]">
      <div
        className="flex h-1.5 w-full overflow-hidden rounded-full bg-surfaceAlt"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={safeTotal || 1}
        aria-valuenow={done}
        aria-label={t("adminBroadcasts.progress.label", {
          sent: formatNumber(sent),
          total: formatNumber(safeTotal),
        })}
      >
        <span className="h-full bg-success" style={{ width: `${pct(sent)}%` }} />
        <span className="h-full bg-danger" style={{ width: `${pct(failed)}%` }} />
        <span className="h-full bg-warning" style={{ width: `${pct(blocked)}%` }} />
      </div>

      {detailed ? (
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-5">
          <Counter label={t("adminBroadcasts.progress.sent")} value={formatNumber(sent)} tone="text-success" />
          <Counter label={t("adminBroadcasts.progress.failed")} value={formatNumber(failed)} tone="text-danger" />
          <Counter label={t("adminBroadcasts.progress.blocked")} value={formatNumber(blocked)} tone="text-warning" />
          <Counter
            label={t("adminBroadcasts.progress.pending")}
            value={formatNumber(Math.max(0, safeTotal - done))}
            tone="text-muted"
          />
          <Counter label={t("adminBroadcasts.progress.total")} value={formatNumber(safeTotal)} tone="text-text" />
        </dl>
      ) : (
        <p className="mt-1 text-xs text-muted">
          {t("adminBroadcasts.progress.label", {
            sent: formatNumber(sent),
            total: formatNumber(safeTotal),
          })}
        </p>
      )}
    </div>
  );
}

function Counter({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className={`font-semibold ${tone}`}>{value}</dd>
    </div>
  );
}
