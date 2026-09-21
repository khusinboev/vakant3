import { lazy, Suspense, useId, useState } from "react";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";

import { useT } from "../../../i18n/useT";

// Reuses the existing resume-KPI dashboard (funnel, latency, diagnostics)
// instead of duplicating it. Lazy so its recharts import — and the three
// queries it fires — only load once the admin actually opens this section;
// the "resume" nav entry (`views/ResumeAnalyticsView.tsx`) renders the same
// component today and can drop it from `registry.ts` once this absorbs it.
const AnalyticsTab = lazy(() => import("../tabs/AnalyticsTab"));

function ResumeKpiFallback() {
  return (
    <div className="space-y-3 p-4">
      <div className="h-40 animate-pulse rounded-2xl bg-surfaceAlt" />
      <div className="h-32 animate-pulse rounded-2xl bg-surfaceAlt" />
    </div>
  );
}

/** Collapsible wrapper so the resume-builder KPIs sit on this dashboard without duplicating them. */
export default function ResumeKpiSection() {
  const t = useT();
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <section className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={panelId}
        className="tap-target flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-text">
          <FileText size={14} className="text-primary" aria-hidden="true" />
          {t("admin.analytics2.resumeKpi.title")}
        </span>
        {open ? (
          <ChevronUp size={16} className="shrink-0 text-muted" aria-hidden="true" />
        ) : (
          <ChevronDown size={16} className="shrink-0 text-muted" aria-hidden="true" />
        )}
      </button>
      {open && (
        <div id={panelId} className="border-t border-border p-4">
          <Suspense fallback={<ResumeKpiFallback />}>
            <AnalyticsTab />
          </Suspense>
        </div>
      )}
    </section>
  );
}
