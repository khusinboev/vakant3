import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Wallet } from "lucide-react";

import { adminKeys, getFinanceOverview } from "../../../api/admin";
import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import QueryState from "../components/QueryState";
import { EmptyState, KeyValue, PeriodSelector, Skeleton, StatTile, periodDays, useQueryState } from "../ui";
import type { PeriodValue } from "../ui";

// recharts stays in its own lazy chunk; nothing here imports it statically.
const OverviewRevenueChart = lazy(() => import("../finance/OverviewRevenueChart"));

const PERIODS: PeriodValue[] = ["7", "30", "90"];

/**
 * Dashboard finance block (viewer+, same gate as the endpoint): revenue tiles,
 * a daily revenue chart and the per-method split. The period lives in the URL
 * (`?fin=30`) and replaces the history entry.
 */
export default function OverviewFinance() {
  const t = useT();
  const { formatNumber, formatMoney } = useLocale();
  const [period, setPeriod] = useQueryState<PeriodValue>("fin", "7", { replace: true });
  const days = PERIODS.includes(period) ? periodDays(period) : 7;

  const query = useQuery({
    queryKey: adminKeys.financeOverview(days),
    queryFn: () => getFinanceOverview(days),
    retry: false,
  });

  return (
    <section className="space-y-2" aria-label={t("admin.dash.fin.title")}>
      <div className="flex items-center justify-between gap-2">
        <Link to="/admin/finance" className="flex items-center gap-1.5 text-[13px] font-semibold text-text">
          <Wallet size={16} aria-hidden="true" className="text-muted" />
          {t("admin.dash.fin.title")}
        </Link>
        <PeriodSelector value={PERIODS.includes(period) ? period : "7"} onChange={setPeriod} periods={PERIODS} />
      </div>

      <QueryState query={query} skeletonClassName="h-40">
        {(data) => {
          const hasPayments = data.paid_all_time.count > 0 || data.series.some((p) => p.paid_sum > 0);
          return (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <StatTile labelKey="admin.dash.fin.today" value={formatMoney(data.paid_today.sum)} />
                <StatTile labelKey="admin.dash.fin.period" value={formatMoney(data.paid_period.sum)} />
                <StatTile labelKey="admin.dash.fin.payments" value={formatNumber(data.paid_period.count)} />
                <StatTile labelKey="admin.dash.fin.proBuyers" value={formatNumber(data.pro_buyers_period)} />
              </div>

              {hasPayments ? (
                <div className="admin-card">
                  <Suspense fallback={<Skeleton height="h-[140px]" />}>
                    <OverviewRevenueChart series={data.series} />
                  </Suspense>
                </div>
              ) : (
                <div className="admin-card">
                  <EmptyState icon={Wallet} labelKey="admin.dash.fin.empty" />
                </div>
              )}

              <KeyValue
                rows={[
                  ...data.by_method.map((row) => {
                    const key = `adminFinance.method.${row.method}` as TranslationKey;
                    const label = t(key);
                    return {
                      label: label === key ? row.method : label,
                      value: `${formatMoney(row.sum)} · ${formatNumber(row.count)}`,
                    };
                  }),
                  { labelKey: "admin.dash.fin.pending", value: formatNumber(data.pending_count) },
                  { labelKey: "admin.dash.fin.cancelled", value: formatNumber(data.cancelled_count) },
                  { labelKey: "admin.dash.fin.allTime", value: formatMoney(data.paid_all_time.sum) },
                  { labelKey: "admin.dash.fin.balance", value: formatMoney(data.balance_outstanding) },
                ]}
              />
            </div>
          );
        }}
      </QueryState>
    </section>
  );
}
