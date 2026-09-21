import { CalendarClock, CheckCircle2, Circle } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import EmptyState from "../components/EmptyState";
import GroupCard from "../components/GroupCard";
import QueryState from "../components/QueryState";
import { useAutoPostSchedule } from "../useAdminQueries";

/** Today's auto-post slots (`GET /admin/auto-post-schedule`), refreshed every 60 s. */
export default function ScheduleCard() {
  const t = useT();
  const locale = useLocale();
  const schedule = useAutoPostSchedule();

  return (
    <GroupCard icon={CalendarClock} title={t("adminAutopost.schedule.title")}>
      <QueryState query={schedule} skeletonClassName="h-40">
        {(data) => (
          <div className="py-2">
            <p className="pb-2 text-xs font-medium text-muted">
              {t("adminAutopost.schedule.postedOf", {
                posted: locale.formatNumber(data.posted_today),
                total: locale.formatNumber(data.total_today),
              })}
            </p>
            {data.schedule.length === 0 ? (
              <EmptyState
                icon={CalendarClock}
                labelKey="adminAutopost.schedule.empty"
                className="py-6"
              />
            ) : (
              <ul className="space-y-1.5">
                {data.schedule.map((slot, index) => (
                  <li
                    key={`${slot.ts}-${index}`}
                    className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface px-3 py-2"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      {slot.done ? (
                        <CheckCircle2 size={15} className="shrink-0 text-success" aria-hidden="true" />
                      ) : (
                        <Circle size={15} className="shrink-0 text-muted" aria-hidden="true" />
                      )}
                      <span className="truncate text-sm text-text">{locale.formatDateTime(slot.ts)}</span>
                      {slot.uid && (
                        <span className="truncate text-xs text-muted" title={slot.uid}>
                          {slot.uid}
                        </span>
                      )}
                    </span>
                    <span
                      className={`shrink-0 text-[11px] font-semibold ${slot.done ? "text-success" : "text-muted"}`}
                    >
                      {t(slot.done ? "adminAutopost.schedule.done" : "adminAutopost.schedule.pending")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </QueryState>
    </GroupCard>
  );
}
