import { useT } from "../../i18n/useT";
import { sourceLabel } from "../../lib/vacancySource";

type Props = { source?: string | null; label?: string | null };

/** Small chip naming where a vacancy comes from (hh.uz gets the accent tone). */
export default function SourceBadge({ source, label }: Props) {
  const t = useT();
  const site = sourceLabel(source, label);
  if (!site) return null;
  const tone = source === "hh" ? "border-danger/30 text-danger" : "border-border text-muted";
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border bg-surfaceAlt px-2 py-0.5 text-[10px] font-semibold ${tone}`}
      title={t("vacancy.source", { site })}
      aria-label={t("vacancy.source", { site })}
    >
      {site}
    </span>
  );
}
