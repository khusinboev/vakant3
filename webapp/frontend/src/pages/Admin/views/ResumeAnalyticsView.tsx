import AnalyticsTab from "../tabs/AnalyticsTab";
import { useAdminHeader } from "../ui";

/**
 * The existing resume-KPI analytics (funnel, latency, diagnostics), rebuilt
 * to the v3 density scale (see `tabs/AnalyticsTab.tsx`). It is the only
 * recharts importer, so it stays a lazy chunk of its own.
 *
 * `pages/AnalyticsPage.tsx` also embeds the same component as a collapsible
 * (`analytics/ResumeKpiSection.tsx`); this route keeps it as a full page for
 * the "resume" nav entry until that entry is retired from `registry.ts`.
 */
export default function ResumeAnalyticsView() {
  useAdminHeader({ titleKey: "admin.nav.resume" });
  return <AnalyticsTab />;
}
