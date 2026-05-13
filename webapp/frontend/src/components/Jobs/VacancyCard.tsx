import { Heart, MapPin } from "lucide-react";

import type { VacancyItem } from "../../types";

type Props = {
  item: VacancyItem;
  onOpen: (uid: string) => void;
  onToggleSave: (uid: string, isSaved: boolean) => void;
};

export default function VacancyCard({ item, onOpen, onToggleSave }: Props) {
  return (
    <article className="card overflow-hidden p-4 transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1 overflow-hidden">
              <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">{item.company}</p>
              <h3 className="mt-1 break-words text-base font-semibold leading-snug text-slate-900 line-clamp-2">{item.title}</h3>
            </div>
            <button
              aria-label={item.is_saved ? "Saqlangan" : "Saqlash"}
              className={`tap-target shrink-0 rounded-full border p-2 transition-colors ${item.is_saved ? "border-red-400 bg-red-50 text-red-500" : "border-slate-300 text-slate-400 hover:border-red-300 hover:text-red-400"}`}
              onClick={() => onToggleSave(item.uid, item.is_saved)}
            >
              <Heart size={16} className={item.is_saved ? "fill-current" : ""} />
            </button>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="rounded-full bg-brand-50 px-2 py-1 font-semibold text-brand-700">{item.salary_text}</span>
            <span className="inline-flex items-center gap-1">
              <MapPin size={14} /> {item.location || item.district || "Hudud ko'rsatilmagan"}
            </span>
            <span className="text-slate-400">•</span>
            <span>{item.posted_at}</span>
          </div>
        </div>
      </div>

      <button onClick={() => onOpen(item.uid)} className="tap-target mt-4 w-full rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white">
        Batafsil ko'rish
      </button>
    </article>
  );
}
