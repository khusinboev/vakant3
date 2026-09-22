import { useT } from "../../../i18n/useT";
import type { ResumeFunnelStep } from "../types";

export type FunnelBarProps = {
  step: ResumeFunnelStep;
  /** Localized step name; falls back to the raw key from the API. */
  name: string;
};

/** One funnel step: completion bar plus entered / dropped-off counts. */
export default function FunnelBar({ step, name }: FunnelBarProps) {
  const t = useT();
  const percent = Math.min(100, Math.max(0, step.completion_rate));

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] font-medium text-muted">{name}</span>
        <span className="text-[11px] font-bold text-text">{step.completion_rate}%</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-surfaceAlt"
        role="progressbar"
        aria-label={name}
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between">
        <span className="text-[11px] text-muted">
          {t("admin.funnel.entered", { n: step.entered_users })}
        </span>
        <span className="text-[11px] text-danger">
          {t("admin.funnel.dropped", { n: step.dropoff_users })}
        </span>
      </div>
    </div>
  );
}
