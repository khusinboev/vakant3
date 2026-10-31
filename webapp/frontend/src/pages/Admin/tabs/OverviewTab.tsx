import { useT } from "../../../i18n/useT";
import QueryState from "../components/QueryState";
import { KeyValue, ProgressBar } from "../ui";
import { useResumeGoals } from "../useAdminQueries";
import type { ResumeGoals } from "../types";

function meters(data: ResumeGoals, t: ReturnType<typeof useT>) {
  return [
    {
      label: t("admin.kpi.completion"),
      value: `${data.completion_rate}%`,
      ok: data.completion_rate_ok,
      progress: data.completion_rate_target > 0 ? (data.completion_rate / data.completion_rate_target) * 100 : 0,
    },
    {
      label: t("admin.kpi.sendSuccess"),
      value: `${data.send_success_rate}%`,
      ok: data.send_success_rate_ok,
      progress:
        data.send_success_rate_target > 0 ? (data.send_success_rate / data.send_success_rate_target) * 100 : 0,
    },
    {
      label: t("admin.kpi.pdfExport"),
      value: `${data.pdf_export_success_rate}%`,
      ok: data.pdf_export_success_rate_ok,
      progress:
        data.pdf_export_success_rate_target > 0
          ? (data.pdf_export_success_rate / data.pdf_export_success_rate_target) * 100
          : 0,
    },
    {
      label: t("admin.kpi.creationTime"),
      value: `${data.median_creation_minutes}${t("admin.kpi.minutesShort")}`,
      ok: data.creation_time_ok,
      // Lower is better: full meter while the median is under target.
      progress:
        data.median_creation_minutes > 0
          ? (data.creation_time_target_minutes / data.median_creation_minutes) * 100
          : 100,
    },
  ];
}

/**
 * Resume-builder KPI goals (funnel completion, send/export success, median
 * creation time) as one row of four compact meters, plus the raw counts they
 * are computed from. Mounted as `Accordion` content on the dashboard
 * (`views/OverviewView.tsx`) — its query only fires once that section opens.
 */
export default function OverviewTab() {
  const t = useT();
  const goals = useResumeGoals();

  return (
    <QueryState query={goals} skeletonClassName="h-24">
      {(data) => (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-2">
            {meters(data, t).map((meter) => (
              <div key={meter.label} className="min-w-0 space-y-1">
                <p className="truncate text-[11px] text-muted">{meter.label}</p>
                <p
                  className={`text-[13px] font-bold tabular-nums ${
                    meter.ok ? "text-success" : "text-danger"
                  }`}
                >
                  {meter.value}
                </p>
                <ProgressBar
                  value={Math.max(0, Math.min(100, Math.round(meter.progress)))}
                  tone={meter.ok ? "success" : "danger"}
                  label={meter.label}
                />
              </div>
            ))}
          </div>

          <KeyValue
            card={false}
            rows={[
              { labelKey: "admin.kpi.openedUsers", value: data.opened_users },
              { labelKey: "admin.kpi.completedUsers", value: data.completed_users },
              { labelKey: "admin.kpi.sendAttempts", value: data.send_attempts },
            ]}
          />
        </div>
      )}
    </QueryState>
  );
}
