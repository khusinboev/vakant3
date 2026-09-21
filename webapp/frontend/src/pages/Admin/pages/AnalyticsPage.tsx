import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { adminKeys, getAnalyticsOverview } from "../../../api/admin";
import { useT } from "../../../i18n/useT";
import PeriodSelector, { type AnalyticsPeriod } from "../analytics/PeriodSelector";
import ResumeKpiSection from "../analytics/ResumeKpiSection";
import StatsGrid from "../analytics/StatsGrid";
import EmptyState from "../components/EmptyState";
import QueryState from "../components/QueryState";

// The dashboard's own chart set (`analytics/Charts.tsx`) is loaded lazily so
// its recharts import gets its own chunk, same reasoning as
// `tabs/AnalyticsTab.tsx` (see that file's header comment).
const Charts = lazy(() => import("../analytics/Charts"));

function ChartsFallback() {
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="h-[268px] animate-pulse rounded-2xl bg-surfaceAlt" />
      ))}
    </div>
  );
}

/**
 * `daily_stats` dashboard: today's live counters as `StatCard`s (with deltas
 * against the period average), the historical series as charts, and the
 * existing resume-builder KPIs folded in underneath so admins don't have to
 * jump to a separate page for them.
 */
export default function AnalyticsPage() {
  const t = useT();
  const [days, setDays] = useState<AnalyticsPeriod>(30);
  const overview = useQuery({
    queryKey: adminKeys.analyticsOverview(days),
    queryFn: () => getAnalyticsOverview(days),
    retry: false,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="sr-only">{t("admin.nav.analytics")}</h1>
        <PeriodSelector value={days} onChange={setDays} />
      </div>

      <QueryState query={overview} skeletonClassName="h-40">
        {(data) => (
          <div className="space-y-4">
            <StatsGrid overview={data} />

            {data.series.length === 0 ? (
              <EmptyState
                icon={BarChart3}
                labelKey="admin.analytics2.empty.title"
                descriptionKey="admin.analytics2.empty.description"
              />
            ) : (
              <Suspense fallback={<ChartsFallback />}>
                <Charts series={data.series} />
              </Suspense>
            )}
          </div>
        )}
      </QueryState>

      <ResumeKpiSection />
    </div>
  );
}
