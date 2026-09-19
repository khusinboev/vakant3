import { AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import FunnelBar from "../components/FunnelBar";
import LatencyChip from "../components/LatencyChip";
import QueryState from "../components/QueryState";
import { useChartColors } from "../components/chartColors";
import { useResumeDiagnostics, useResumeFunnel, useResumeMetrics } from "../useAdminQueries";

/**
 * The only tab that imports recharts. `src/pages/Admin/index.tsx` loads it with
 * React.lazy so the ~300 KB charting library gets its own chunk instead of
 * riding along in the Admin entry chunk.
 */
export default function AnalyticsTab() {
  const t = useT();
  const { formatDateTime } = useLocale();
  const colors = useChartColors();
  const metrics = useResumeMetrics();
  const funnel = useResumeFunnel();
  const diagnostics = useResumeDiagnostics();

  const stepName = (step: string) => {
    const key = `admin.funnel.step.${step}` as TranslationKey;
    const label = t(key);
    return label === key ? step : label;
  };

  return (
    <div className="space-y-4">
      <QueryState query={metrics} skeletonClassName="h-48">
        {(data) => (
          <>
            <section className="card p-4">
              <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted">
                {t("admin.analytics.opsTitle")}
              </h2>
              <div className="mb-3 flex gap-4 text-xs text-muted">
                <span className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
                  {t("admin.analytics.success")}
                </span>
                <span className="flex items-center gap-1.5">
                  <span aria-hidden="true" className="h-2 w-2 rounded-full bg-danger" />
                  {t("admin.analytics.error")}
                </span>
              </div>
              <ResponsiveContainer width="100%" height={130}>
                <BarChart
                  data={[
                    {
                      name: t("admin.analytics.opSave"),
                      ok: data.save_success_24h,
                      err: data.save_error_24h,
                    },
                    {
                      name: t("admin.analytics.opSend"),
                      ok: data.send_success_24h,
                      err: data.send_error_24h,
                    },
                    {
                      name: t("admin.analytics.opExport"),
                      ok: data.export_success_24h,
                      err: data.export_error_24h,
                    },
                  ]}
                  barSize={22}
                  barGap={4}
                  margin={{ top: 4, right: 4, left: -22, bottom: 0 }}
                >
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: colors.muted }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: colors.muted }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
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
                  />
                  <Bar
                    dataKey="ok"
                    fill={colors.success}
                    radius={[4, 4, 0, 0]}
                    name={t("admin.analytics.success")}
                  />
                  <Bar
                    dataKey="err"
                    fill={colors.danger}
                    radius={[4, 4, 0, 0]}
                    name={t("admin.analytics.error")}
                  />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 grid grid-cols-3 divide-x divide-border border-t border-border pt-3 text-center">
                <div>
                  <p className="text-lg font-bold text-text">{data.unique_users_24h}</p>
                  <p className="text-[10px] text-muted">{t("admin.analytics.activeUsers")}</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-text">{data.opened_24h}</p>
                  <p className="text-[10px] text-muted">{t("admin.analytics.opened")}</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-text">{data.ready_24h}</p>
                  <p className="text-[10px] text-muted">{t("admin.analytics.ready")}</p>
                </div>
              </div>
            </section>

            <section className="card p-4">
              <h2 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted">
                <Clock size={11} aria-hidden="true" />
                {t("admin.analytics.latencyTitle")}
              </h2>
              <div className="grid grid-cols-4 gap-2">
                <LatencyChip label={t("admin.latency.ttfi")} ms={data.avg_ttfi_ms} />
                <LatencyChip label={t("admin.latency.save")} ms={data.avg_save_latency_ms} />
                <LatencyChip label={t("admin.latency.send")} ms={data.avg_send_latency_ms} />
                <LatencyChip label={t("admin.latency.export")} ms={data.avg_export_latency_ms} />
              </div>
            </section>
          </>
        )}
      </QueryState>

      <section className="card p-4">
        <QueryState query={funnel} skeletonClassName="h-40">
          {(data) => (
            <>
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-widest text-muted">
                {t("admin.analytics.funnelTitle", { hours: data.window_hours })}
              </h2>
              {data.steps.length === 0 ? (
                <p className="text-xs text-muted">{t("admin.analytics.funnelEmpty")}</p>
              ) : (
                <div className="space-y-4">
                  {data.steps.map((step) => (
                    <FunnelBar key={step.step} step={step} name={stepName(step.step)} />
                  ))}
                </div>
              )}
            </>
          )}
        </QueryState>
      </section>

      <QueryState query={diagnostics} skeletonClassName="h-24">
        {(data) =>
          data.items.length === 0 ? (
            <div className="flex items-center gap-3 rounded-2xl border border-success/30 bg-success/10 p-4">
              <CheckCircle size={18} className="shrink-0 text-success" aria-hidden="true" />
              <p className="text-sm text-success">{t("admin.analytics.noErrors")}</p>
            </div>
          ) : (
            <section className="rounded-2xl border border-danger/30 bg-surface p-4 shadow-sm">
              <h2 className="mb-3 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-widest text-danger">
                <AlertTriangle size={11} aria-hidden="true" />
                {t("admin.analytics.diagTitle")}
              </h2>
              <ul className="space-y-2">
                {data.items.map((item, index) => (
                  <li
                    key={`${item.source}-${item.status}-${index}`}
                    className="rounded-xl border border-danger/30 bg-danger/10 p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-xs font-semibold text-danger">
                        {item.source} / {item.status}
                      </p>
                      <span className="shrink-0 rounded-full bg-danger/15 px-1.5 py-0.5 text-[10px] font-bold text-danger">
                        {t("admin.analytics.diagCount", { n: item.count_24h })}
                      </span>
                    </div>
                    <p className="mt-1 break-words text-xs text-danger">{item.error_text}</p>
                    <p className="mt-1 text-[10px] text-muted">
                      {formatDateTime(item.last_seen_at)}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          )
        }
      </QueryState>
    </div>
  );
}
