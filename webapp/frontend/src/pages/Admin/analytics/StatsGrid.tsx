import type { AnalyticsOverview } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { StatTile } from "../ui";
import { computeDelta, seriesAverage, type NumericStatKey } from "./metrics";

type StatDef = {
  key: NumericStatKey;
  labelKey: TranslationKey;
  /** Formats the value with the currency word instead of a plain number. */
  money?: boolean;
};

// 3-up grid (spec §4b: "9 StatCard → 3 ustunli StatTile"), no icon slot.
const STATS: StatDef[] = [
  { key: "new_users", labelKey: "admin.analytics2.stat.newUsers" },
  { key: "active_users", labelKey: "admin.analytics2.stat.activeUsers" },
  { key: "pro_users", labelKey: "admin.analytics2.stat.proUsers" },
  { key: "revenue", labelKey: "admin.analytics2.stat.revenue", money: true },
  { key: "saves", labelKey: "admin.analytics2.stat.saves" },
  { key: "resume_sends_ok", labelKey: "admin.analytics2.stat.resumeSendsOk" },
  { key: "resume_sends_err", labelKey: "admin.analytics2.stat.resumeSendsErr" },
  { key: "auto_posts", labelKey: "admin.analytics2.stat.autoPosts" },
  { key: "notifications", labelKey: "admin.analytics2.stat.notifications" },
];

export type StatsGridProps = {
  overview: AnalyticsOverview;
};

/**
 * Today's live counters (`compute_day`, never persisted) against each metric's
 * average over the selected period's completed days (`daily_stats`). With no
 * completed days yet (a fresh rollup) the deltas are hidden rather than shown
 * as a misleading +/-100%.
 */
export default function StatsGrid({ overview }: StatsGridProps) {
  const t = useT();
  const { formatNumber, formatMoney } = useLocale();
  const hasBaseline = overview.series.length > 0;

  return (
    <div className="grid grid-cols-3 gap-2" role="list" aria-label={t("admin.analytics2.stat.groupLabel")}>
      {STATS.map((stat) => {
        const value = Number(overview.today[stat.key]) || 0;
        const baseline = seriesAverage(overview.series, stat.key);
        const delta = hasBaseline ? computeDelta(value, baseline) : null;
        return (
          <div key={stat.key} role="listitem">
            <StatTile
              labelKey={stat.labelKey}
              value={stat.money ? formatMoney(value) : formatNumber(value)}
              delta={delta}
              hint={t("admin.analytics2.stat.hintToday")}
            />
          </div>
        );
      })}
    </div>
  );
}
