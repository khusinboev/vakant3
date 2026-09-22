import { useT } from "../../../i18n/useT";

export type LatencyChipProps = {
  label: string;
  ms: number;
};

function tone(ms: number): string {
  if (ms <= 0) return "border-border bg-surfaceAlt text-muted";
  if (ms < 500) return "border-success/30 bg-success/10 text-success";
  if (ms < 1500) return "border-warning/30 bg-warning/10 text-warning";
  return "border-danger/30 bg-danger/10 text-danger";
}

/** One average-latency tile, colored by a fixed good/warn/bad threshold. */
export default function LatencyChip({ label, ms }: LatencyChipProps) {
  const t = useT();
  return (
    <div className={`rounded-xl border px-2 py-2 text-center ${tone(ms)}`}>
      <p className="text-[13px] font-bold">{ms > 0 ? ms : "–"}</p>
      <p className="text-[11px] font-medium">{t("admin.latency.unit")}</p>
      <p className="mt-0.5 text-[11px] opacity-80">{label}</p>
    </div>
  );
}
