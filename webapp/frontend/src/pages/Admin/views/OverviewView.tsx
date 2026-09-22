import { Megaphone, Radio, Send } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { adminKeys, getAnalyticsOverview, getSystemInfo } from "../../../api/admin";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { computeDelta, seriesAverage } from "../analytics/metrics";
import Sparkline from "../analytics/Sparkline";
import QueryState from "../components/QueryState";
import OverviewTab from "../tabs/OverviewTab";
import { Accordion, KeyValue, List, ListRow, StatTile, StatusDot, Toolbar, useAdminHeader } from "../ui";
import { useAdminState, useAutoPostSchedule } from "../useAdminQueries";

/** The dashboard's own window — independent of the Analytics page's PeriodSelector. */
const DASH_DAYS = 7;

/**
 * `/admin` — the panel's front door. 2×2 today tiles, a 7-day trend line,
 * three quick actions, a one-line system status, the auto-post/referral
 * summary and the resume-builder KPIs (folded under a closed accordion so
 * they never push the tiles below the fold on a phone).
 */
export default function OverviewView() {
  const t = useT();
  const navigate = useNavigate();
  const { formatNumber, formatMoney } = useLocale();

  useAdminHeader({ titleKey: "admin.nav.overview" });

  const overview = useQuery({
    queryKey: adminKeys.analyticsOverview(DASH_DAYS),
    queryFn: () => getAnalyticsOverview(DASH_DAYS),
    retry: false,
  });
  const state = useAdminState();
  const schedule = useAutoPostSchedule();
  const system = useQuery({
    queryKey: adminKeys.system(),
    queryFn: getSystemInfo,
    retry: false,
    refetchInterval: 60_000,
  });

  const systemTone = system.data ? (system.data.redis ? "success" : "warning") : "neutral";
  const systemLabel = system.data
    ? t(system.data.redis ? "admin.dash.systemOk" : "admin.dash.systemDegraded")
    : t("admin.dash.systemUnknown");

  return (
    <div className="space-y-3">
      <QueryState query={overview} skeletonClassName="h-40">
        {(data) => {
          const hasBaseline = data.series.length > 0;
          const delta = (key: "new_users" | "active_users" | "pro_users" | "revenue") =>
            hasBaseline ? computeDelta(Number(data.today[key]) || 0, seriesAverage(data.series, key)) : null;

          return (
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <StatTile
                  labelKey="admin.analytics2.stat.newUsers"
                  value={formatNumber(data.today.new_users)}
                  delta={delta("new_users")}
                />
                <StatTile
                  labelKey="admin.analytics2.stat.activeUsers"
                  value={formatNumber(data.today.active_users)}
                  delta={delta("active_users")}
                />
                <StatTile
                  labelKey="admin.analytics2.stat.proUsers"
                  value={formatNumber(data.today.pro_users)}
                  delta={delta("pro_users")}
                />
                <StatTile
                  labelKey="admin.analytics2.stat.revenue"
                  value={formatMoney(data.today.revenue)}
                  delta={delta("revenue")}
                />
              </div>

              <div className="admin-card">
                <Sparkline
                  points={data.series.map((point) => point.new_users)}
                  ariaLabel={t("admin.dash.sparklineAria")}
                />
                <p className="mt-1 text-[11px] text-muted">{t("admin.dash.sparklineLabel")}</p>
              </div>
            </div>
          );
        }}
      </QueryState>

      <Toolbar
        name="dash.quick"
        max={3}
        items={[
          {
            id: "autopost",
            labelKey: "admin.more.quick.postNow",
            icon: Send,
            onClick: () => navigate("/admin/autopost"),
          },
          {
            id: "broadcast",
            labelKey: "admin.more.quick.newBroadcast",
            icon: Megaphone,
            onClick: () => navigate("/admin/broadcasts/new"),
          },
          {
            id: "channel",
            labelKey: "admin.more.quick.addChannel",
            icon: Radio,
            onClick: () => navigate("/admin/channels"),
          },
        ]}
      />

      <List card>
        <ListRow
          leading={<StatusDot tone={systemTone} />}
          title={systemLabel}
          to="/admin/system"
        />
      </List>

      <QueryState query={state} skeletonClassName="h-24">
        {(data) => (
          <KeyValue
            rows={[
              {
                labelKey: "admin.dash.autoPostLabel",
                value: t(data.auto_post_enabled ? "admin.status.on" : "admin.status.off"),
                tone: data.auto_post_enabled ? "success" : "neutral",
              },
              {
                labelKey: "admin.dash.postedTodayLabel",
                value: schedule.data ? `${schedule.data.posted_today}/${schedule.data.total_today}` : "—",
                hidden: !schedule.data,
              },
              {
                labelKey: "admin.dash.referralLabel",
                value: t(data.referral_enabled ? "admin.status.on" : "admin.status.off"),
                tone: data.referral_enabled ? "success" : "neutral",
              },
              {
                labelKey: "admin.dash.minReferralsLabel",
                value: data.referral_required_count,
              },
            ]}
          />
        )}
      </QueryState>

      <Accordion
        queryKey="dashSection"
        items={[
          {
            id: "resumeKpi",
            titleKey: "admin.overview.kpiTitle",
            content: <OverviewTab />,
          },
        ]}
      />
    </div>
  );
}
