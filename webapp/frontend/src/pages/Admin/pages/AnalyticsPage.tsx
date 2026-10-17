import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";

import { adminKeys, getAnalyticsOverview } from "../../../api/admin";
import ResumeKpiSection from "../analytics/ResumeKpiSection";
import StatsGrid from "../analytics/StatsGrid";
import QueryState from "../components/QueryState";
import { EmptyState, PeriodSelector, Skeleton, periodDays, useAdminHeader, useQueryState, type PeriodValue } from "../ui";

// The dashboard's own chart set (`analytics/Charts.tsx`) is loaded lazily so
// its recharts import gets its own chunk, same reasoning as
// `tabs/AnalyticsTab.tsx` (see that file's header comment).
const Charts = lazy(() => import("../analytics/Charts"));

function ChartsFallback() {
  return <Skeleton rows={4} />;
}

/**
 * `daily_stats` dashboard: today's live counters as `StatTile`s (with deltas
 * against the period average), the historical series as charts inside an
 * accordion, and the existing resume-builder KPIs folded in underneath as a
 * separate collapsible so admins don't have to jump to a separate page for
 * them.
 */
export default function AnalyticsPage() {
  const [period, setPeriod] = useQueryState<PeriodValue>("period", "30");
  const days = periodDays(period);

  useAdminHeader({ titleKey: "admin.nav.analytics" });

  const overview = useQuery({
    queryKey: adminKeys.analyticsOverview(days),
    queryFn: () => getAnalyticsOverview(days),
    retry: false,
  });

  return (
    <div className="space-y-3">
      <PeriodSelector value={period} onChange={setPeriod} periods={["7", "30", "90"]} />

      <QueryState query={overview} skeletonClassName="h-40">
        {(data) => (
          <div className="space-y-3">
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
