import { useT } from "../../../i18n/useT";

export type KpiDonutProps = {
  value: number;
  target: number;
  /** The API decides pass/fail; lower-is-better metrics work too. */
  ok: boolean;
  label: string;
  unit?: string;
  /**
   * Ring fill in percent, for metrics where `value / target` is not the
   * progress (e.g. creation time, where lower is better).
   */
  progress?: number;
};

const RADIUS = 26;
const STROKE = 9;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * A progress-against-target ring.
 *
 * Deliberately a hand-rolled SVG: the old version pulled the whole of recharts
 * into the Overview tab (and therefore into the Admin entry chunk) just to
 * draw two arcs. Colors come from the semantic tokens, so both themes work.
 */
export default function KpiDonut({
  value,
  target,
  ok,
  label,
  unit = "%",
  progress,
}: KpiDonutProps) {
  const t = useT();
  const raw = progress ?? (target > 0 ? (value / target) * 100 : 0);
  const fill = Math.min(100, Math.max(0, Math.round(raw)));
  const tone = ok ? "text-success" : "text-danger";

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative h-[72px] w-[72px]">
        <svg
          viewBox="0 0 72 72"
          className={`h-[72px] w-[72px] ${tone}`}
          role="img"
          aria-label={`${label}: ${value}${unit} — ${t("admin.kpi.target", { target: `${target}${unit}` })}`}
        >
          <g transform="rotate(-90 36 36)">
            <circle
              cx="36"
              cy="36"
              r={RADIUS}
              fill="none"
              strokeWidth={STROKE}
              className="stroke-current opacity-20"
            />
            <circle
              cx="36"
              cy="36"
              r={RADIUS}
              fill="none"
              strokeWidth={STROKE}
              strokeLinecap="round"
              className="stroke-current"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={CIRCUMFERENCE * (1 - fill / 100)}
            />
          </g>
        </svg>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className={`text-[13px] font-extrabold leading-none ${tone}`}>
            {value}
            {unit}
          </span>
        </div>
      </div>
      <span className="text-center text-[10px] leading-tight text-muted">{label}</span>
    </div>
  );
}
