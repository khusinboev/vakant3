import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { useChartColors } from "../components/chartColors";
import type { FinanceSeriesPoint } from "../../../api/adminTypes";

export type FinanceChartProps = {
  series: FinanceSeriesPoint[];
};

/**
 * Revenue (line, left axis, money) vs. activations (bars, right axis, count)
 * over the selected period. The only recharts user on this page — it rides
 * inside `FinancePage`'s own lazy chunk (see `registry.ts`), so recharts never
 * loads for pages other than Finance/Analytics.
 */
export default function FinanceChart({ series }: FinanceChartProps) {
  const t = useT();
  const { formatMoney, formatNumber, formatDate } = useLocale();
  const colors = useChartColors();

  const hasData = series.some((point) => point.revenue > 0 || point.activations > 0);

  return (
    <section className="card p-4">
      <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted">
        {t("adminFinance.chart.title")}
      </h2>
      <div className="mb-3 flex gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
          {t("adminFinance.chart.revenue")}
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-primary" />
          {t("adminFinance.chart.activations")}
        </span>
      </div>

      {!hasData ? (
        <p className="py-10 text-center text-xs text-muted">{t("adminFinance.chart.empty")}</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={series} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
            <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="day"
              tickFormatter={(value: string) => formatDate(value, { day: "2-digit", month: "2-digit" })}
              tick={{ fontSize: 10, fill: colors.muted }}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
            />
            <YAxis
              yAxisId="money"
              tick={{ fontSize: 10, fill: colors.muted }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => formatNumber(value)}
              width={54}
            />
            <YAxis
              yAxisId="count"
              orientation="right"
              tick={{ fontSize: 10, fill: colors.muted }}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
              width={36}
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
              cursor={{ fill: colors.cursor }}
              labelFormatter={(value) => formatDate(String(value))}
              formatter={(value, name) => [
                name === t("adminFinance.chart.revenue") ? formatMoney(Number(value)) : formatNumber(Number(value)),
                name,
              ]}
            />
            <Bar
              yAxisId="count"
              dataKey="activations"
              name={t("adminFinance.chart.activations")}
              fill={colors.primary}
              radius={[4, 4, 0, 0]}
              barSize={14}
            />
            <Line
              yAxisId="money"
              type="monotone"
              dataKey="revenue"
              name={t("adminFinance.chart.revenue")}
              stroke={colors.success}
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
