import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DailyStatsPoint } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { useChartColors, type ChartColors } from "../components/chartColors";
import { Accordion } from "../ui";
import { shortDay, tickInterval } from "./metrics";

/**
 * The dashboard's own recharts import, separate from `tabs/AnalyticsTab`'s.
 * `AnalyticsPage` loads this with `React.lazy` so the ~300 KB charting
 * library never rides along in the page's own chunk, only in this one.
 *
 * Each chart lives in its own `Accordion` item (spec §4b: "4 ta 268px grafik
 * → Accordion ostida, bittadan") — only the open one mounts its
 * `ResponsiveContainer`.
 */
export type ChartsProps = {
  series: DailyStatsPoint[];
};

function axisProps(colors: ChartColors) {
  return {
    tick: { fontSize: 10, fill: colors.muted },
    tickLine: false,
    axisLine: false,
  };
}

export default function Charts({ series }: ChartsProps) {
  const t = useT();
  const colors = useChartColors();
  const { formatMoney, formatNumber } = useLocale();
  const data = series.map((point) => ({ ...point, label: shortDay(point.day) }));
  const interval = tickInterval(data.length);

  const tooltipStyle = {
    contentStyle: {
      fontSize: 12,
      borderRadius: 12,
      background: colors.surface,
      border: `1px solid ${colors.border}`,
      color: colors.text,
    },
    labelStyle: { color: colors.text },
    itemStyle: { color: colors.text },
  };

  const legendStyle = { fontSize: 11, color: colors.muted };

  return (
    <Accordion
      queryKey="analyticsChart"
      items={[
        {
          id: "users",
          titleKey: "admin.analytics2.chart.usersTitle",
          content: (
            <div role="img" aria-label={t("admin.analytics2.chart.usersAria")} className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid stroke={colors.border} strokeDasharray="4 6" vertical={false} />
                  <XAxis dataKey="label" interval={interval} {...axisProps(colors)} />
                  <YAxis allowDecimals={false} {...axisProps(colors)} />
                  <Tooltip {...tooltipStyle} cursor={{ stroke: colors.muted, strokeOpacity: 0.3 }} />
                  <Legend wrapperStyle={legendStyle} />
                  <Line
                    type="monotone"
                    dataKey="new_users"
                    name={t("admin.analytics2.chart.usersNew")}
                    stroke={colors.primary}
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="active_users"
                    name={t("admin.analytics2.chart.usersActive")}
                    stroke={colors.muted}
                    strokeWidth={2}
                    strokeDasharray="5 4"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ),
        },
        {
          id: "revenue",
          titleKey: "admin.analytics2.chart.revenueTitle",
          content: (
            <div role="img" aria-label={t("admin.analytics2.chart.revenueAria")} className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid stroke={colors.border} strokeDasharray="4 6" vertical={false} />
                  <XAxis dataKey="label" interval={interval} {...axisProps(colors)} />
                  <YAxis allowDecimals={false} {...axisProps(colors)} />
                  <Tooltip
                    {...tooltipStyle}
                    cursor={{ fill: colors.cursor }}
                    formatter={(v) => formatMoney(Number(v))}
                  />
                  <Bar
                    dataKey="revenue"
                    name={t("admin.analytics2.chart.revenueTitle")}
                    fill={colors.primary}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ),
        },
        {
          id: "resumeSends",
          titleKey: "admin.analytics2.chart.resumeSendsTitle",
          content: (
            <div
              role="img"
              aria-label={t("admin.analytics2.chart.resumeSendsAria")}
              className="h-[220px] w-full"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid stroke={colors.border} strokeDasharray="4 6" vertical={false} />
                  <XAxis dataKey="label" interval={interval} {...axisProps(colors)} />
                  <YAxis allowDecimals={false} {...axisProps(colors)} />
                  <Tooltip {...tooltipStyle} cursor={{ fill: colors.cursor }} />
                  <Legend wrapperStyle={legendStyle} />
                  <Bar
                    dataKey="resume_sends_ok"
                    name={t("admin.analytics2.chart.resumeOk")}
                    stackId="sends"
                    fill={colors.success}
                    radius={[0, 0, 0, 0]}
                  />
                  <Bar
                    dataKey="resume_sends_err"
                    name={t("admin.analytics2.chart.resumeErr")}
                    stackId="sends"
                    fill={colors.danger}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ),
        },
        {
          id: "notifications",
          titleKey: "admin.analytics2.chart.notifTitle",
          content: (
            <div role="img" aria-label={t("admin.analytics2.chart.notifAria")} className="h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} barGap={4} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                  <CartesianGrid stroke={colors.border} strokeDasharray="4 6" vertical={false} />
                  <XAxis dataKey="label" interval={interval} {...axisProps(colors)} />
                  <YAxis allowDecimals={false} {...axisProps(colors)} />
                  <Tooltip
                    {...tooltipStyle}
                    cursor={{ fill: colors.cursor }}
                    formatter={(v) => formatNumber(Number(v))}
                  />
                  <Legend wrapperStyle={legendStyle} />
                  <Bar
                    dataKey="notifications"
                    name={t("admin.analytics2.chart.notifNotifications")}
                    fill={colors.primary}
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="auto_posts"
                    name={t("admin.analytics2.chart.notifAutoPosts")}
                    fill={colors.muted}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ),
        },
      ]}
    />
  );
}
