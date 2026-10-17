import { TONE_DOT, type Tone } from "./Chip";

export type ProgressBarProps = {
  value: number;
  max?: number;
  tone?: Tone;
  /** Accessible name; the bar is `role="progressbar"`. */
  label?: string;
  className?: string;
};

/** The one 4px progress bar (broadcast progress, KPI meters). */
export default function ProgressBar({
  value,
  max = 100,
  tone = "primary",
  label,
  className = "",
}: ProgressBarProps) {
  const safeMax = max > 0 ? max : 1;
  const percent = Math.max(0, Math.min(100, Math.round((value / safeMax) * 100)));
  return (
    <div
      role="progressbar"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
      className={`h-1 w-full overflow-hidden rounded-full bg-surfaceAlt ${className}`}
    >
      <div
        className={`h-full rounded-full transition-[width] ${TONE_DOT[tone]}`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}
