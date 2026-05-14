import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import LoginPrompt from "../components/LoginPrompt";
import SearchFilters from "../components/Jobs/SearchFilters";
import VacancyCard from "../components/Jobs/VacancyCard";
import VacancyDetail from "../components/Jobs/VacancyDetail";
import { useJobs } from "../hooks/useJobs";
import { useSaves } from "../hooks/useSaves";
import { useAuthStore } from "../store/auth";

function SkeletonCard() {
  return (
    <div className="card animate-pulse p-4 space-y-3">
      <div className="h-3 w-1/3 rounded bg-slate-200" />
      <div className="h-5 w-2/3 rounded bg-slate-200" />
      <div className="h-3 w-1/2 rounded bg-slate-200" />
      <div className="mt-2 h-10 rounded-2xl bg-slate-200" />
    </div>
  );
}

export default function Home() {
  const [filters, setFilters] = useState({
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
  const telegramUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  const canUseSaves = isAuthenticated || Boolean(telegramUserId);

  // Debounce text search — call API 400ms after user stops typing
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(filters.query.trim()), 400);
    return () => clearTimeout(t);
  }, [filters.query]);

  const queryParams = {
    q: debouncedQuery,
    specs: filters.specs,
    region_soato: filters.region_soato,
    district_soato: filters.district_soato,
    money: filters.money,
    sort_key: filters.sort_key,
    sort_type: filters.sort_type,
  };

  const jobs = useJobs(queryParams);
  const { save, remove } = useSaves(1, 10, canUseSaves);

  // Flatten all pages into a single list
  const vacancies = jobs.data?.pages.flatMap((p) => p.vacancies) ?? [];
  const lastPage = jobs.data?.pages[jobs.data.pages.length - 1];
  const hasMore = jobs.hasNextPage;

  // IntersectionObserver sentinel — when it enters the viewport, load next page
  const sentinelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !jobs.isFetchingNextPage) {
          jobs.fetchNextPage();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, jobs]);

  const detail = useQuery({
    queryKey: ["jobs", "detail", activeUid],
    queryFn: async () => {
      const { data } = await client.get(`/jobs/${activeUid}`);
      return data as { uid: string; data: Record<string, unknown> };
    },
    enabled: Boolean(activeUid),
  });

  const toggleSave = (uid: string, saved: boolean) => {
    if (!canUseSaves) {
      setShowLoginPrompt(true);
      return;
    }
    if (saved) remove.mutate(uid);
    else save.mutate(uid);
  };

  return (
    <div className="space-y-3">
      <SearchFilters
        value={filters}
        onChange={(next) => {
          setFilters(next);
        }}
      />

      {jobs.isError && (
        <div className="card p-4 text-sm text-red-600">
          Natijalar yuklanmadi. Qayta urinib ko'ring.
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>
          {jobs.isLoading
            ? "Yuklanmoqda..."
            : jobs.isFetchingNextPage
              ? "Yuklanmoqda..."
              : `${lastPage?.total_estimate ?? vacancies.length} ta vakansiya`}
        </span>
        <span>
          {lastPage ? `${lastPage.page} / ${lastPage.last_page || 1}` : ""}
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
              <div className="card col-span-full p-6 text-center text-sm text-slate-500">
                Natija topilmadi. Boshqa kalit so'z yoki filtr sinab ko'ring.
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
            <p className="pb-2 text-center text-xs text-slate-400">
              Barcha natijalar ko'rsatildi
            </p>
          )}
        </>
      )}

      <VacancyDetail
        open={Boolean(activeUid)}
        onClose={() => setActiveUid("")}
        data={detail.data ?? null}
        isLoading={detail.isLoading && Boolean(activeUid)}
      />

      {showLoginPrompt && (
        <LoginPrompt onClose={() => setShowLoginPrompt(false)} />
      )}
    </div>
  );
}
