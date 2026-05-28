import { useState } from "react";
import { Trash2 } from "lucide-react";

import LoginPrompt from "../components/LoginPrompt";
import VacancyDetail from "../components/Jobs/VacancyDetail";
import { useSaves } from "../hooks/useSaves";
import { useAuthStore } from "../store/auth";

function fmtSalary(min: unknown, max: unknown): string {
  const fmt = (v: number) => v.toLocaleString("ru");
  if (typeof min === "number" && typeof max === "number") {
    return `${fmt(min)} - ${fmt(max)} so'm`;
  }
  if (typeof min === "number") return `${fmt(min)} so'mdan`;
  return "Kelishiladi";
}

export default function Saves() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authUser = useAuthStore((s) => s.user);
  const telegramUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  const canUseSaves = isAuthenticated || Boolean(telegramUserId ?? authUser?.user_id);
  const [showPrompt, setShowPrompt] = useState(false);
  const [activeItem, setActiveItem] = useState<{
    uid: string;
    data: Record<string, unknown>;
  } | null>(null);
  const { list, remove } = useSaves(1, 20, canUseSaves);

  if (!canUseSaves) {
    return (
      <>
        <div className="card flex flex-col items-center gap-4 p-8 text-center">
          <p className="text-base font-semibold text-slate-700">Saqlangan ishlar</p>
          <p className="text-sm text-slate-500">
            Bu bo'lim faqat Telegram ichidan ochilganda ishlaydi.
          </p>
          <button
            className="tap-target rounded-2xl bg-brand-500 px-5 py-3 text-sm font-semibold text-white"
            onClick={() => setShowPrompt(true)}
          >
            Kirish
          </button>
        </div>
        {showPrompt && <LoginPrompt onClose={() => setShowPrompt(false)} />}
      </>
    );
  }

  if (list.isLoading) {
    return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  }

  if (list.isError) {
    return (
      <div className="card p-4 text-sm text-red-600">
        Saqlangan ishlarni yuklab bo'lmadi.
      </div>
    );
  }

  if (!list.data?.items.length) {
    return (
      <div className="card p-4 text-sm">
        Saqlangan ishlar yo'q. Ishlarni saqlash uchun heart tugmasini bosing.
      </div>
    );
  }

  return (
    <>
      <div className="grid gap-3 md:grid-cols-2">
        {list.data.items.map((item) => {
          const d = item.data;
          const companyObj = d.company as Record<string, unknown> | null | undefined;
          const districtObj = d.soato_district as Record<string, unknown> | null | undefined;
          const regionObj = d.soato_region as Record<string, unknown> | null | undefined;
          const company = String(companyObj?.name || "");
          const district = String(districtObj?.name_uz || "");
          const region = String(regionObj?.name_uz || "");
          const location =
            [district, region].filter(Boolean).join(", ") ||
            String(d.address || "");
          const salary = fmtSalary(d.min_salary, d.max_salary);

          return (
            <article key={item.uid} className="card p-4">
              {company && (
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  {company}
                </p>
              )}
              <p className="mt-0.5 text-sm font-semibold leading-snug text-slate-900 line-clamp-2">
                {String(d.title || "Vakansiya")}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-brand-50 px-2 py-1 font-semibold text-brand-700">
                  {salary}
                </span>
                {location && (
                  <span className="text-slate-500">{location}</span>
                )}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  className="tap-target flex-1 rounded-2xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white"
                  onClick={() => setActiveItem({ uid: item.uid, data: d })}
                >
                  Batafsil
                </button>
                <button
                  className="tap-target inline-flex items-center gap-1.5 rounded-2xl border border-red-300 px-3 py-2.5 text-sm text-red-600"
                  onClick={() => remove.mutate(item.uid)}
                  aria-label="O'chirish"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <VacancyDetail
        open={Boolean(activeItem)}
        onClose={() => setActiveItem(null)}
        data={activeItem}
        isLoading={false}
      />
    </>
  );
}
