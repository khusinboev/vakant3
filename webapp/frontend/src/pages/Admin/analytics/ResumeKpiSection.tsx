import { lazy, Suspense } from "react";

import { Accordion, Skeleton } from "../ui";

// Reuses the existing resume-KPI dashboard (funnel, latency, diagnostics)
// instead of duplicating it. Lazy so its recharts import — and the three
// queries it fires — only load once the admin actually opens this section;
// the "resume" nav entry (`views/ResumeAnalyticsView.tsx`) renders the same
// component today and can drop it from `registry.ts` once this absorbs it.
const AnalyticsTab = lazy(() => import("../tabs/AnalyticsTab"));

function ResumeKpiFallback() {
  return <Skeleton rows={4} />;
}

/** Collapsible wrapper so the resume-builder KPIs sit on this dashboard without duplicating them. */
export default function ResumeKpiSection() {
  return (
    <Accordion
      queryKey="analyticsResumeKpi"
      items={[
        {
          id: "resumeKpi",
          titleKey: "admin.analytics2.resumeKpi.title",
          content: (
            <Suspense fallback={<ResumeKpiFallback />}>
              <AnalyticsTab nested />
            </Suspense>
          ),
        },
      ]}
    />
  );
}
