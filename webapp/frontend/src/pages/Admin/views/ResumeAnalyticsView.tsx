import AnalyticsTab from "../tabs/AnalyticsTab";

/**
 * The existing resume-KPI analytics (funnel, latency, diagnostics), migrated
 * into the shell unchanged. It is the only recharts importer, so it stays a
 * lazy chunk of its own.
 *
 * The Analytics page agent owns `pages/AnalyticsPage.tsx` (the `daily_stats`
 * dashboard); once that page absorbs these cards this entry can be dropped
 * from `registry.ts`.
 */
export default function ResumeAnalyticsView() {
  return <AnalyticsTab />;
}
