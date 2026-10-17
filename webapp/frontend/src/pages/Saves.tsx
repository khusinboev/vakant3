import { useState } from "react";
import { Trash2 } from "lucide-react";

import LoginPrompt from "../components/LoginPrompt";
import VacancyDetail from "../components/Jobs/VacancyDetail";
import { useSaves } from "../hooks/useSaves";
import { useT } from "../i18n/useT";
import { useLocale } from "../i18n/useLocale";
import { useAuthStore } from "../store/auth";
import type { VacancyDetailResponse } from "../types";

export default function Saves() {
  const t = useT();
  const { formatNumber } = useLocale();

  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authUser = useAuthStore((s) => s.user);
  const initData = window.Telegram?.WebApp?.initData;
  const canUseSaves = isAuthenticated || Boolean(initData) || Boolean(authUser?.user_id);

  const [showPrompt, setShowPrompt] = useState(false);
  const [activeItem, setActiveItem] = useState<VacancyDetailResponse | null>(null);
  const { list, remove } = useSaves(1, 20, canUseSaves);

  const fmtSalary = (min: unknown, max: unknown): string => {
    if (typeof min === "number" && typeof max === "number") {
      return t("vacancy.salary.range", { min: formatNumber(min), max: formatNumber(max) });
    }
    if (typeof min === "number") return t("vacancy.salary.from", { min: formatNumber(min) });
    return t("vacancy.salary.negotiable");
  };

  if (!canUseSaves) {
    return (
      <>
        <div className="card flex flex-col items-center gap-4 p-8 text-center">
          <p className="text-base font-semibold text-text">{t("saves.title")}</p>
          <p className="text-sm text-muted">{t("saves.tgOnly")}</p>
          <button
            type="button"
            className="tap-target rounded-2xl bg-primary px-5 py-3 text-sm font-semibold text-primaryFg"
            onClick={() => setShowPrompt(true)}
          >
            {t("saves.login")}
          </button>
        </div>
        {showPrompt && <LoginPrompt onClose={() => setShowPrompt(false)} />}
      </>
    );
  }

  if (list.isLoading) {
    return <div className="card p-4 text-sm text-muted">{t("common.loading")}</div>;
  }

  if (list.isError) {
    return <div className="card p-4 text-sm text-danger">{t("saves.error")}</div>;
  }

  if (!list.data?.items.length) {
    return <div className="card p-4 text-sm text-muted">{t("saves.empty")}</div>;
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
          const district = String(districtObj?.name || districtObj?.name_uz || "");
          const region = String(regionObj?.name || regionObj?.name_uz || "");
          const location = [district, region].filter(Boolean).join(", ") || String(d.address || "");
          const salary = fmtSalary(d.min_salary, d.max_salary);

          return (
            <article key={item.uid} className="card p-4">
              {company && (
                <p className="text-xs font-medium uppercase tracking-wide text-muted">{company}</p>
              )}
              <p className="mt-0.5 text-sm font-semibold leading-snug text-text line-clamp-2">
                {String(d.title || t("vacancy.fallbackTitle"))}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-primary/10 px-2 py-1 font-semibold text-primary">
                  {salary}
                </span>
                {location && <span className="text-muted">{location}</span>}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  className="tap-target flex-1 rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-primaryFg"
                  onClick={() => setActiveItem({ uid: item.uid, data: d })}
                >
                  {t("common.details")}
                </button>
                <button
                  type="button"
                  className="tap-target inline-flex items-center gap-1.5 rounded-2xl border border-danger/40 px-3 py-2.5 text-sm text-danger"
                  onClick={() => remove.mutate(item.uid)}
                  aria-label={t("common.delete")}
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
