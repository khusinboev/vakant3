import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Clock, Database, RadioTower, Server } from "lucide-react";

import { adminKeys, getSystemInfo } from "../../../api/admin";
import { useT } from "../../../i18n/useT";
import { useLocale } from "../../../i18n/useLocale";
import GroupCard from "../components/GroupCard";
import QueryState from "../components/QueryState";
import StatCard from "../components/StatCard";
import JsonDetails from "./JsonDetails";
import { formatBytes, formatUptime } from "./format";

const REFRESH_MS = 30_000;

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <span className="min-w-0 shrink-0 text-sm text-text">{label}</span>
      <span className="min-w-0 truncate text-right text-sm text-muted">{value}</span>
    </div>
  );
}

/** System health: DB footprint, table counts, background scheduler state, env. */
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

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted">{t("adminSystem.health.autoRefresh")}</p>

      <QueryState query={query} skeletonClassName="h-64">
        {(info) => (
          <div className="space-y-4">
            <GroupCard icon={Database} title={t("adminSystem.health.dbTitle")} divide={false}>
              <div className="grid grid-cols-2 gap-2.5 py-3 sm:grid-cols-3">
                <StatCard labelKey="adminSystem.health.dbSize" value={formatBytes(info.db.size_bytes)} />
                <StatCard labelKey="adminSystem.health.walSize" value={formatBytes(info.db.wal_bytes)} />
                <StatCard
                  labelKey="adminSystem.health.pageCount"
                  value={formatNumber(info.db.page_count)}
                />
              </div>
            </GroupCard>

            <GroupCard icon={Server} title={t("adminSystem.health.countsTitle")} divide={false}>
              <div className="grid grid-cols-2 gap-2.5 py-3 sm:grid-cols-4">
                <StatCard labelKey="adminSystem.health.users" value={formatNumber(info.counts.users)} />
                <StatCard
                  labelKey="adminSystem.health.sessions"
                  value={formatNumber(info.counts.sessions)}
                />
                <StatCard
                  labelKey="adminSystem.health.resumeEvents"
                  value={formatNumber(info.counts.resume_events)}
                />
                <StatCard
                  labelKey="adminSystem.health.broadcastsRunning"
                  value={formatNumber(info.counts.broadcasts_running)}
                />
              </div>
            </GroupCard>

            <GroupCard icon={Clock} title={t("adminSystem.health.schedulersTitle")}>
              <Row
                label={t("adminSystem.health.autoPost")}
                value={
                  <span className="inline-flex items-center gap-2">
                    {lastRun(info.schedulers.auto_post.last_run)}
                    <JsonDetails
                      data={info.schedulers.auto_post.next_slots}
                      labelKey="adminSystem.health.viewRaw"
                    />
                  </span>
                }
              />
              <Row
                label={t("adminSystem.health.scheduledDay")}
                value={info.schedulers.auto_post.scheduled_day ?? never}
              />
              <Row
                label={t("adminSystem.health.nextSlots")}
                value={formatNumber(info.schedulers.auto_post.next_slots.length)}
              />
              <Row
                label={t("adminSystem.health.notifications")}
                value={lastRun(info.schedulers.notifications.last_run)}
              />
              <Row
                label={t("adminSystem.health.weeklyStats")}
                value={info.schedulers.weekly_stats.last_week ?? never}
              />
            </GroupCard>

            <GroupCard icon={RadioTower} title={t("adminSystem.health.envTitle")}>
              <Row
                label={t("adminSystem.health.redis")}
                value={t(info.redis ? "admin.status.on" : "admin.status.off")}
              />
              <Row label={t("adminSystem.health.version")} value={info.version ?? "—"} />
              <Row label={t("adminSystem.health.uptime")} value={formatUptime(info.uptime, t)} />
            </GroupCard>
          </div>
        )}
      </QueryState>
    </div>
  );
}
