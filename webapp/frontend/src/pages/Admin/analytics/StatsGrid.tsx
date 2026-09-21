import type { ElementType } from "react";
import { Activity, Bell, Bookmark, Crown, FileCheck2, FileX2, Send, UserPlus, Wallet } from "lucide-react";

import type { AnalyticsOverview } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import StatCard from "../components/StatCard";
import { computeDelta, seriesAverage, type NumericStatKey } from "./metrics";

type StatDef = {
  key: NumericStatKey;
  labelKey: TranslationKey;
  icon: ElementType;
  /** Formats the value with the currency word instead of a plain number. */
  money?: boolean;
};

const STATS: StatDef[] = [
  { key: "new_users", labelKey: "admin.analytics2.stat.newUsers", icon: UserPlus },
  { key: "active_users", labelKey: "admin.analytics2.stat.activeUsers", icon: Activity },
  { key: "pro_users", labelKey: "admin.analytics2.stat.proUsers", icon: Crown },
  { key: "revenue", labelKey: "admin.analytics2.stat.revenue", icon: Wallet, money: true },
  { key: "saves", labelKey: "admin.analytics2.stat.saves", icon: Bookmark },
  { key: "resume_sends_ok", labelKey: "admin.analytics2.stat.resumeSendsOk", icon: FileCheck2 },
  { key: "resume_sends_err", labelKey: "admin.analytics2.stat.resumeSendsErr", icon: FileX2 },
  { key: "auto_posts", labelKey: "admin.analytics2.stat.autoPosts", icon: Send },
  { key: "notifications", labelKey: "admin.analytics2.stat.notifications", icon: Bell },
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
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3" role="list" aria-label={t("admin.analytics2.stat.groupLabel")}>
      {STATS.map((stat) => {
        const value = Number(overview.today[stat.key]) || 0;
        const baseline = seriesAverage(overview.series, stat.key);
        const delta = hasBaseline ? computeDelta(value, baseline) : null;
        return (
          <div key={stat.key} role="listitem">
            <StatCard
              labelKey={stat.labelKey}
              icon={stat.icon}
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
