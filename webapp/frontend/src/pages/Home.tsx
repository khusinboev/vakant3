import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import LoginPrompt from "../components/LoginPrompt";
import SearchFilters, { type SearchFilterValue } from "../components/Jobs/SearchFilters";
import VacancyCard from "../components/Jobs/VacancyCard";
import VacancyDetail from "../components/Jobs/VacancyDetail";
import BottomSheet from "../components/ui/BottomSheet";
import { useJobDetail, useJobs } from "../hooks/useJobs";
import { useSaves } from "../hooks/useSaves";
import { useT } from "../i18n/useT";
import { FREE_SAVE_LIMIT } from "../lib/constants";
import { useAuthStore } from "../store/auth";

function SkeletonCard() {
  return (
    <div className="card animate-pulse space-y-3 p-4">
      <div className="h-3 w-1/3 rounded bg-surfaceAlt" />
      <div className="h-5 w-2/3 rounded bg-surfaceAlt" />
      <div className="h-3 w-1/2 rounded bg-surfaceAlt" />
      <div className="mt-2 h-10 rounded-2xl bg-surfaceAlt" />
    </div>
  );
}

export default function Home() {
  const t = useT();
  const navigate = useNavigate();

  const [filters, setFilters] = useState<SearchFilterValue>({
    query: "",
    specs: "",
    region_soato: "",
    district_soato: "",
    money: 0,
    sort_key: "",
    sort_type: "",
  });
  const [activeUid, setActiveUid] = useState("");
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authUser = useAuthStore((state) => state.user);
  const initData = window.Telegram?.WebApp?.initData;
  const canUseSaves = isAuthenticated || Boolean(initData) || Boolean(authUser?.user_id);

  // Debounce text search — call API 400ms after user stops typing
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(filters.query.trim()), 400);
    return () => clearTimeout(timer);
  }, [filters.query]);

  const jobs = useJobs({
    q: debouncedQuery,
    specs: filters.specs,
    region_soato: filters.region_soato,
    district_soato: filters.district_soato,
    money: filters.money,
    sort_key: filters.sort_key,
    sort_type: filters.sort_type,
  });
  const { save, remove, saveLimitReached, clearSaveLimitReached } = useSaves(1, 10, canUseSaves);

  const vacancies = jobs.data?.pages.flatMap((p) => p.vacancies) ?? [];
  const lastPage = jobs.data?.pages[jobs.data.pages.length - 1];
  const hasMore = jobs.hasNextPage;

  // IntersectionObserver sentinel — when it enters the viewport, load next page
  const sentinelRef = useRef<HTMLDivElement>(null);
  const fetchNextPage = jobs.fetchNextPage;
  const isFetchingNextPage = jobs.isFetchingNextPage;
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isFetchingNextPage) {
          void fetchNextPage();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, isFetchingNextPage, fetchNextPage]);

  const detail = useJobDetail(activeUid);

  const toggleSave = (uid: string, saved: boolean) => {
    if (!canUseSaves) {
      setShowLoginPrompt(true);
      return;
    }
    if (saved) remove.mutate(uid);
    else save.mutate(uid);
  };

  const isLocked = vacancies.find((v) => v.uid === activeUid)?.is_pro_locked ?? false;

  return (
    <div className="space-y-3">
      <SearchFilters value={filters} onChange={setFilters} />

      {jobs.isError && (
        <div className="card p-4 text-sm text-danger">{t("home.errorLoad")}</div>
      )}

      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          {jobs.isLoading || jobs.isFetchingNextPage
            ? t("common.loading")
            : t("home.count", { n: lastPage?.total_estimate ?? vacancies.length })}
        </span>
        <span>
          {lastPage ? t("home.page", { page: lastPage.page, total: lastPage.last_page || 1 }) : ""}
        </span>
      </div>

      {jobs.isLoading ? (
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </section>
      ) : (
        <>
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {vacancies.map((item) => (
              <VacancyCard
                key={item.uid}
                item={item}
                onOpen={setActiveUid}
                onToggleSave={toggleSave}
              />
            ))}
            {vacancies.length === 0 && !jobs.isError && (
              <div className="card col-span-full p-6 text-center text-sm text-muted">
                {t("home.empty")}
              </div>
            )}
          </section>

          {/* Sentinel: IntersectionObserver triggers next page load here */}
          <div ref={sentinelRef} className="py-1" />

          {jobs.isFetchingNextPage && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          )}

          {!hasMore && vacancies.length > 0 && (
            <p className="pb-2 text-center text-xs text-muted">{t("home.allShown")}</p>
          )}
        </>
      )}

      <VacancyDetail
        open={Boolean(activeUid)}
        onClose={() => setActiveUid("")}
        data={detail.data ?? null}
        isLoading={detail.isLoading && Boolean(activeUid)}
        isLocked={isLocked}
      />

      {showLoginPrompt && <LoginPrompt onClose={() => setShowLoginPrompt(false)} />}

      <BottomSheet
        open={saveLimitReached}
        onClose={clearSaveLimitReached}
        ariaLabel={t("home.saveLimitTitle", { current: FREE_SAVE_LIMIT, limit: FREE_SAVE_LIMIT })}
      >
        <div className="text-center">
          <div className="mb-3 text-3xl">📌</div>
          <p className="text-base font-bold text-text">
            {t("home.saveLimitTitle", { current: FREE_SAVE_LIMIT, limit: FREE_SAVE_LIMIT })}
          </p>
          <p className="mt-1 text-sm text-muted">
            {t("home.saveLimitBody", { limit: FREE_SAVE_LIMIT })}
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <button
              type="button"
              className="tap-target w-full rounded-2xl bg-primary py-3 text-sm font-semibold text-primaryFg"
              onClick={() => {
                clearSaveLimitReached();
                navigate("/wallet");
              }}
            >
              💎 {t("home.goPro")}
            </button>
            <button
              type="button"
              className="tap-target w-full rounded-2xl bg-surfaceAlt py-3 text-sm font-medium text-text"
              onClick={clearSaveLimitReached}
            >
              {t("common.close")}
            </button>
          </div>
        </div>
      </BottomSheet>
    </div>
  );
}
