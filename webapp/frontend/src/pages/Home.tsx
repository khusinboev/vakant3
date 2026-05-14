import { useState } from "react";
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

export default function Home() {
  const [filters, setFilters] = useState({ query: "", specs: "", region_soato: "", district_soato: "", money: 0, sort_key: "", sort_type: "" });
  const [page, setPage] = useState(1);
  const [activeUid, setActiveUid] = useState("");
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const jobs = useJobs({ ...filters, page });
  const { save, remove } = useSaves();

  const queryText = filters.query.trim().toLowerCase();
  const filteredVacancies = (jobs.data?.vacancies || []).filter((item) => {
    if (!queryText) return true;
    return [item.title, item.company, item.location, item.district]
      .map((part) => String(part || "").toLowerCase())
      .some((part) => part.includes(queryText));
  });

  const detail = useQuery({
    queryKey: ["jobs", "detail", activeUid],
    queryFn: async () => {
      const { data } = await client.get(`/jobs/${activeUid}`);
      return data as { uid: string; data: Record<string, unknown> };
    },
    enabled: Boolean(activeUid)
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

      {jobs.isError && <div className="card p-4 text-sm text-red-600">Natijalar yuklanmadi. Qayta urinib ko'ring</div>}

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{jobs.isLoading ? "Yuklanmoqda..." : `${filteredVacancies.length || 0} ta vakansiya`}</span>
        <span>{jobs.data ? `Sahifa ${page} / ${jobs.data.last_page || 1}` : ""}</span>
      </div>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filteredVacancies.map((item) => (
          <VacancyCard key={item.uid} item={item} onOpen={setActiveUid} onToggleSave={toggleSave} />
        ))}
      </section>

      <Pagination page={page} lastPage={jobs.data?.last_page || 1} onChange={setPage} />

      <VacancyDetail open={Boolean(activeUid)} onClose={() => setActiveUid("")} data={detail.data || null} />

      {showLoginPrompt && <LoginPrompt onClose={() => setShowLoginPrompt(false)} />}
    </div>
  );
}
