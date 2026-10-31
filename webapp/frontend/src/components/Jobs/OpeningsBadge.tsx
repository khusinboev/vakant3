import { Users } from "lucide-react";

import { useT } from "../../i18n/useT";

type Props = { count?: number | null };

/** Chip with the number of openings collapsed into one card (shown only above 1). */
export default function OpeningsBadge({ count }: Props) {
  const t = useT();
  if (typeof count !== "number" || !Number.isFinite(count) || count <= 1) return null;
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-xs font-semibold text-success">
      <Users size={12} aria-hidden="true" /> {t("vacancy.openings", { n: count })}
    </span>
  );
}
