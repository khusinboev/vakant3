import { Heart, Lock, MapPin } from "lucide-react";

import { useT } from "../../i18n/useT";
import type { VacancyItem } from "../../types";

type Props = {
  item: VacancyItem;
  onOpen: (uid: string) => void;
  onToggleSave: (uid: string, isSaved: boolean) => void;
};

export default function VacancyCard({ item, onOpen, onToggleSave }: Props) {
  const t = useT();
  const location = item.location || item.district || t("vacancy.noRegion");

  return (
    <article className={`card overflow-hidden p-4 transition hover:-translate-y-0.5 hover:shadow-md ${item.is_pro_locked ? "opacity-80" : ""}`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center gap-2">
                <p className="truncate text-xs font-medium uppercase tracking-wide text-muted">{item.company}</p>
                {item.is_pro_locked && (
                  <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-bold text-warning">
                    <Lock size={10} /> PRO
                  </span>
                )}
              </div>
              <h3 className="mt-1 break-words text-base font-semibold leading-snug text-text line-clamp-2">
                {item.is_pro_locked ? `🔒 ${t("vacancy.hidden")}` : item.title}
              </h3>
            </div>
            <button
              type="button"
              aria-label={item.is_saved ? t("vacancy.saved") : t("vacancy.save")}
              aria-pressed={item.is_saved}
              className={`tap-target shrink-0 rounded-full border p-2 transition-colors ${item.is_saved ? "border-danger/50 bg-danger/10 text-danger" : "border-border text-muted hover:border-danger/40 hover:text-danger"}`}
              onClick={() => onToggleSave(item.uid, item.is_saved)}
            >
              <Heart size={16} className={item.is_saved ? "fill-current" : ""} />
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className={`rounded-full px-2 py-1 font-semibold ${item.is_pro_locked ? "bg-warning/15 text-warning" : "bg-primary/10 text-primary"}`}>
              {item.salary_text || t("vacancy.salary.negotiable")}
            </span>
            <span className="inline-flex items-center gap-1">
              <MapPin size={14} /> {location}
            </span>
            {item.posted_at && (
              <>
                <span className="text-muted/60">•</span>
                <span>{item.posted_at}</span>
              </>
            )}
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => onOpen(item.uid)}
        className={`tap-target mt-4 w-full rounded-2xl px-4 py-3 text-sm font-semibold ${
          item.is_pro_locked ? "bg-warning text-white dark:text-bg" : "bg-primary text-primaryFg"
        }`}
      >
        {item.is_pro_locked ? `🔒 ${t("vacancy.openPro")}` : t("vacancy.open")}
      </button>
    </article>
  );
}
