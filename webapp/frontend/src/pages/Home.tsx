import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import LoginPrompt from "../components/LoginPrompt";
import Pagination from "../components/Jobs/Pagination";
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
  const [page, setPage] = useState(1);
  const [activeUid, setActiveUid] = useState("");
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Debounce the text search — only call API 400ms after user stops typing
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      const trimmed = filters.query.trim();
      setDebouncedQuery((prev) => {
        if (prev !== trimmed) setPage(1);
        return trimmed;
      });
    }, 400);
    return () => clearTimeout(t);
  }, [filters.query]);

  const jobs = useJobs({
    q: debouncedQuery,
    specs: filters.specs,
    region_soato: filters.region_soato,
    district_soato: filters.district_soato,
    money: filters.money,
    sort_key: filters.sort_key,
    sort_type: filters.sort_type,
    page,
  });
  const { save, remove } = useSaves();

  const vacancies = jobs.data?.vacancies ?? [];

  const detail = useQuery({
    queryKey: ["jobs", "detail", activeUid],
    queryFn: async () => {
      const { data } = await client.get(`/jobs/${activeUid}`);
      return data as { uid: string; data: Record<string, unknown> };
    },
    enabled: Boolean(activeUid),
  });

  const toggleSave = (uid: string, saved: boolean) => {
    if (!isAuthenticated) {
      setShowLoginPrompt(true);
      return;
    }
    if (saved) {
      remove.mutate(uid);
    } else {
      save.mutate(uid);
    }
  };

  return (
    <div className="space-y-3">
      <SearchFilters
        value={filters}
        onChange={(next) => {
          setPage(1);
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
            : jobs.isFetching
              ? "Yangilanmoqda..."
              : `${jobs.data?.total_estimate ?? 0} ta vakansiya`}
        </span>
        <span>
          {jobs.data ? `Sahifa ${page} / ${jobs.data.last_page || 1}` : ""}
        </span>
      </div>

      {jobs.isLoading ? (
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </section>
      ) : (
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
      )}

      <Pagination
        page={page}
        lastPage={jobs.data?.last_page ?? 1}
        onChange={setPage}
      />

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
