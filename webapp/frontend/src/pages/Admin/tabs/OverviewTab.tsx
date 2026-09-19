import { GitBranch, Megaphone } from "lucide-react";

import { useT } from "../../../i18n/useT";
import KpiDonut from "../components/KpiDonut";
import QueryState from "../components/QueryState";
import { useAutoPostSchedule, useResumeGoals } from "../useAdminQueries";
import type { AdminState, AutoPostScheduleItem } from "../types";

function StatusPill({ on, label }: { on: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
        on ? "bg-success/15 text-success" : "bg-surfaceAlt text-muted"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${on ? "bg-success" : "bg-muted"}`}
      />
      {label}
    </span>
  );
}

function slotTone(item: AutoPostScheduleItem): string {
  if (item.done && item.uid) return "bg-success/15 text-success";
  if (item.done) return "bg-surfaceAlt text-muted";
  return "border border-border bg-surface text-muted";
}

export default function OverviewTab({ state }: { state: AdminState }) {
  const t = useT();
  const schedule = useAutoPostSchedule();
  const goals = useResumeGoals();

  const posted = schedule.data;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="card p-4">
          <div className="mb-2 flex items-center gap-1.5">
            <Megaphone size={13} className="text-primary" aria-hidden="true" />
            <span className="text-xs font-semibold text-muted">{t("admin.overview.autoPost")}</span>
          </div>
          <StatusPill
            on={state.auto_post_enabled}
            label={state.auto_post_enabled ? t("admin.status.on") : t("admin.status.off")}
          />
          {posted && (
            <p className="mt-2 text-xs text-muted">
              {t("admin.overview.postedToday", {
                posted: posted.posted_today,
                total: posted.total_today,
              })}
            </p>
          )}
        </div>

        <div className="card p-4">
          <div className="mb-2 flex items-center gap-1.5">
            <GitBranch size={13} className="text-primary" aria-hidden="true" />
            <span className="text-xs font-semibold text-muted">{t("admin.overview.referral")}</span>
          </div>
          <StatusPill
            on={state.referral_enabled}
            label={state.referral_enabled ? t("admin.status.on") : t("admin.status.off")}
          />
          <p className="mt-2 text-xs text-muted">
            {t("admin.overview.minRefs", { count: state.referral_required_count })}
          </p>
        </div>
      </div>

      <section className="card p-4">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-muted">
          {t("admin.overview.scheduleTitle")}
        </h2>
        <QueryState query={schedule} skeletonClassName="h-16">
          {(data) =>
            data.schedule.length === 0 ? (
              <p className="text-xs text-muted">{t("admin.overview.scheduleEmpty")}</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {data.schedule.map((item) => (
                  <li
                    key={item.ts}
                    title={t(
                      item.done && item.uid
                        ? "admin.overview.slotPosted"
                        : item.done
                          ? "admin.overview.slotSkipped"
                          : "admin.overview.slotPending",
                      { time: item.time_str },
                    )}
                    className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${slotTone(item)}`}
                  >
                    <span aria-hidden="true">
                      {item.done && item.uid ? "✓" : item.done ? "–" : "○"}
                    </span>
                    {item.time_str}
                  </li>
                ))}
              </ul>
            )
          }
        </QueryState>
      </section>

      <section className="card p-4">
        <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-muted">
          {t("admin.overview.kpiTitle")}
        </h2>
        <QueryState query={goals} skeletonClassName="h-48">
          {(data) => (
            <>
              <div className="grid grid-cols-2 gap-4">
                <KpiDonut
                  value={data.completion_rate}
                  target={data.completion_rate_target}
                  ok={data.completion_rate_ok}
                  label={t("admin.kpi.completion")}
                />
                <KpiDonut
                  value={data.send_success_rate}
                  target={data.send_success_rate_target}
                  ok={data.send_success_rate_ok}
                  label={t("admin.kpi.sendSuccess")}
                />
                <KpiDonut
                  value={data.pdf_export_success_rate}
                  target={data.pdf_export_success_rate_target}
                  ok={data.pdf_export_success_rate_ok}
                  label={t("admin.kpi.pdfExport")}
                />
                <KpiDonut
                  value={data.median_creation_minutes}
                  target={data.creation_time_target_minutes}
                  ok={data.creation_time_ok}
                  label={t("admin.kpi.creationTime")}
                  unit={t("admin.kpi.minutesShort")}
                  // Lower is better: full ring while the median is under target.
                  progress={
                    data.median_creation_minutes > 0
                      ? (data.creation_time_target_minutes / data.median_creation_minutes) * 100
                      : 100
                  }
                />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
                <div>
                  <p className="text-base font-bold text-text">{data.opened_users}</p>
                  <p className="text-[10px] text-muted">{t("admin.kpi.openedUsers")}</p>
                </div>
                <div>
                  <p className="text-base font-bold text-text">{data.completed_users}</p>
                  <p className="text-[10px] text-muted">{t("admin.kpi.completedUsers")}</p>
                </div>
                <div>
                  <p className="text-base font-bold text-text">{data.send_attempts}</p>
                  <p className="text-[10px] text-muted">{t("admin.kpi.sendAttempts")}</p>
                </div>
              </div>
            </>
          )}
        </QueryState>
      </section>
    </div>
  );
}
