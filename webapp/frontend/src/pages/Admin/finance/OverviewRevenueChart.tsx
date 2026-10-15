import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { FinanceOverviewPoint } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { useChartColors } from "../components/chartColors";

/**
 * Daily paid top-ups as an area chart for the dashboard. The only recharts
 * importer on the Overview; loaded with `React.lazy` so it stays in the
 * `vendor-charts` chunk.
 */
export default function OverviewRevenueChart({ series }: { series: FinanceOverviewPoint[] }) {
  const t = useT();
  const { formatMoney, formatNumber, formatDate } = useLocale();
  const colors = useChartColors();
  const label = t("admin.dash.fin.revenue");

  return (
    <div role="img" aria-label={t("admin.dash.fin.chartAria")}>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={series} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
          <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="day"
            tickFormatter={(value: string) => formatDate(value, { day: "2-digit", month: "2-digit" })}
            tick={{ fontSize: 11, fill: colors.muted }}
            tickLine={false}
            axisLine={false}
            minTickGap={24}
          />
          <YAxis
            tick={{ fontSize: 11, fill: colors.muted }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => formatNumber(value)}
            width={54}
          />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 12,
              background: colors.surface,
              border: `1px solid ${colors.border}`,
              color: colors.text,
            }}
            labelStyle={{ color: colors.text }}
            itemStyle={{ color: colors.text }}
            labelFormatter={(value) => formatDate(String(value))}
            formatter={(value) => [formatMoney(Number(value)), label]}
          />
          <Area
            type="monotone"
            dataKey="paid_sum"
            name={label}
            stroke={colors.success}
            fill={colors.success}
            fillOpacity={0.15}
            strokeWidth={2}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
