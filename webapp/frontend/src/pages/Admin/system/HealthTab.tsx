import { useQuery } from "@tanstack/react-query";

import { adminKeys, getSystemInfo } from "../../../api/admin";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import QueryState from "../components/QueryState";
import { Accordion, JsonDetails, KeyValue, StatusDot, type Tone } from "../ui";
import { formatBytes, formatUptime } from "./format";

const REFRESH_MS = 30_000;

function SectionLabel({ children }: { children: string }) {
  return <p className="px-0.5 text-[11px] font-bold uppercase tracking-wider text-muted">{children}</p>;
}

/** System health: DB footprint, table counts, environment, background schedulers. */
export default function HealthTab() {
  const t = useT();
  const { formatDateTime, formatNumber } = useLocale();
  const query = useQuery({
    queryKey: adminKeys.system(),
    queryFn: getSystemInfo,
    retry: false,
    refetchInterval: REFRESH_MS,
  });

  const never = t("adminSystem.health.never");
  const lastRun = (value: number | null) => (value === null ? never : formatDateTime(value));
  const schedulerTone = (value: number | null): Tone => (value === null ? "warning" : "success");

  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted">{t("adminSystem.health.autoRefresh")}</p>

      <QueryState query={query} skeletonClassName="h-64">
        {(info) => (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <SectionLabel>{t("adminSystem.health.dbTitle")}</SectionLabel>
              <KeyValue
                rows={[
                  { labelKey: "adminSystem.health.dbSize", value: formatBytes(info.db.size_bytes) },
                  { labelKey: "adminSystem.health.walSize", value: formatBytes(info.db.wal_bytes) },
                  { labelKey: "adminSystem.health.pageCount", value: formatNumber(info.db.page_count) },
                ]}
              />
            </div>

            <div className="space-y-1.5">
              <SectionLabel>{t("adminSystem.health.countsTitle")}</SectionLabel>
              <KeyValue
                rows={[
                  { labelKey: "adminSystem.health.users", value: formatNumber(info.counts.users) },
                  { labelKey: "adminSystem.health.sessions", value: formatNumber(info.counts.sessions) },
                  {
                    labelKey: "adminSystem.health.resumeEvents",
                    value: formatNumber(info.counts.resume_events),
                  },
                  {
                    labelKey: "adminSystem.health.broadcastsRunning",
                    value: formatNumber(info.counts.broadcasts_running),
                  },
                ]}
              />
            </div>

            <div className="space-y-1.5">
              <SectionLabel>{t("adminSystem.health.envTitle")}</SectionLabel>
              <KeyValue
                rows={[
                  {
                    labelKey: "adminSystem.health.redis",
                    value: (
                      <StatusDot
                        tone={info.redis ? "success" : "danger"}
                        labelKey={info.redis ? "admin.status.on" : "admin.status.off"}
                      />
                    ),
                  },
                  { labelKey: "adminSystem.health.version", value: info.version ?? "—" },
                  { labelKey: "adminSystem.health.uptime", value: formatUptime(info.uptime, t) },
                ]}
              />
            </div>

            <Accordion
              queryKey="healthSection"
              items={[
                {
                  id: "schedulers",
                  titleKey: "adminSystem.health.schedulersTitle",
                  summary: lastRun(info.schedulers.auto_post.last_run),
                  content: (
                    <div className="space-y-2">
                      <KeyValue
                        card={false}
                        rows={[
                          {
                            labelKey: "adminSystem.health.autoPost",
                            value: (
                              <span className="inline-flex items-center gap-1.5">
                                <StatusDot tone={schedulerTone(info.schedulers.auto_post.last_run)} />
                                {lastRun(info.schedulers.auto_post.last_run)}
                              </span>
                            ),
                          },
                          {
                            labelKey: "adminSystem.health.scheduledDay",
                            value: info.schedulers.auto_post.scheduled_day ?? never,
                          },
                          {
                            labelKey: "adminSystem.health.nextSlots",
                            value: formatNumber(info.schedulers.auto_post.next_slots.length),
                          },
                          {
                            labelKey: "adminSystem.health.notifications",
                            value: (
                              <span className="inline-flex items-center gap-1.5">
                                <StatusDot tone={schedulerTone(info.schedulers.notifications.last_run)} />
                                {lastRun(info.schedulers.notifications.last_run)}
                              </span>
                            ),
                          },
                          {
                            labelKey: "adminSystem.health.weeklyStats",
                            value: info.schedulers.weekly_stats.last_week ?? never,
                          },
                        ]}
                      />
                      <JsonDetails
                        data={info.schedulers.auto_post.next_slots}
                        labelKey="adminSystem.health.viewRaw"
                      />
                    </div>
                  ),
                },
              ]}
            />
          </div>
        )}
      </QueryState>
    </div>
  );
}
