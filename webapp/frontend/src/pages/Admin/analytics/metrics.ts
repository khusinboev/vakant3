import type { DailyStatsPoint } from "../../../api/adminTypes";

/** Every numeric field of a rollup day (i.e. not the `day` key or `computed_at` timestamp). */
export type NumericStatKey = Exclude<keyof DailyStatsPoint, "day" | "computed_at">;

/** Mean of `key` across the completed days in `series` (0 when there is no history yet). */
export function seriesAverage(series: DailyStatsPoint[], key: NumericStatKey): number {
  if (series.length === 0) return 0;
  const sum = series.reduce((total, point) => total + (Number(point[key]) || 0), 0);
  return sum / series.length;
}

/**
 * Percent change of `current` vs. `baseline` (the previous-period daily
 * average). Returns `null` when there's no meaningful baseline to compare
 * against — a zero baseline would otherwise divide to `Infinity`/`NaN` — so
 * callers hide the delta pill instead of showing a nonsense number.
 */
export function computeDelta(current: number, baseline: number): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(baseline)) return null;
  if (baseline === 0) return current === 0 ? 0 : null;
  return ((current - baseline) / baseline) * 100;
}

/** `"2026-09-21"` -> `"09-21"`, used as compact x-axis tick labels. */
export function shortDay(day: string): string {
  return day.length >= 5 ? day.slice(5) : day;
}

/** Keeps ~6 visible x-axis ticks regardless of the selected period length. */
export function tickInterval(pointCount: number): number {
  return Math.max(0, Math.ceil(pointCount / 6) - 1);
}
