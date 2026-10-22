import { CalendarClock } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import QueryState from "../components/QueryState";
import { StatusChip } from "../ui/Chip";
import EmptyState from "../ui/EmptyState";

import { useAutoPostSchedule } from "../useAdminQueries";

/** Today's auto-post slots (`GET /admin/auto-post-schedule`), refreshed every 60 s. */
export default function AutoPostSlots() {
  const t = useT();
  const locale = useLocale();
  const schedule = useAutoPostSchedule();

  return (
    <QueryState query={schedule} skeletonClassName="h-20">
      {(data) => (
        <div className="admin-card space-y-2">
          <p className="text-[11px] font-medium text-muted">
            {t("adminAutopost.schedule.postedOf", {
              posted: locale.formatNumber(data.posted_today),
              total: locale.formatNumber(data.total_today),
            })}
          </p>
          {data.schedule.length === 0 ? (
            <EmptyState icon={CalendarClock} labelKey="adminAutopost.schedule.empty" />
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {data.schedule.map((slot, index) => (
                <StatusChip
                  key={`${slot.ts}-${index}`}
                  status={slot.done ? "done" : "pending"}
                  label={slot.time_str}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </QueryState>
  );
}
