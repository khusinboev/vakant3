import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import client from "../api/client";
import { useLang } from "../i18n/useT";
import { JOBS_LIST_KEY } from "./useSaves";
import type { VacancyDetailResponse, VacancyItem } from "../types";

export type JobsParams = {
  q: string;
  money: number;
  region_soato: string;
  district_soato: string;
  specs: string;
  sort_key: string;
  sort_type: string;
};

type JobsPage = { vacancies: VacancyItem[]; page: number; last_page: number; total_estimate: number };

/**
 * Infinite vacancy list.
 * Key: ["jobs","list",lang,params] — namespaced so optimistic save patches never
 * touch ["jobs","detail",uid,lang], which holds a completely different shape.
 *
 * Localized responses carry the language in the key AND send it as `?lang`:
 * the API prefers `?lang` over `users.lang`, so a refetch fired right after a
 * language switch cannot race the `PATCH /profile/lang` and cache the old one.
 */
export function useJobs(params: JobsParams) {
  const lang = useLang();
  return useInfiniteQuery<JobsPage>({
    queryKey: [...JOBS_LIST_KEY, lang, params],
    queryFn: async ({ pageParam = 1 }) => {
      const { data } = await client.get<JobsPage>("/jobs/search", {
        params: { ...params, page: pageParam, lang },
      });
      return data;
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.last_page ? lastPage.page + 1 : undefined,
    staleTime: 2 * 60 * 1000,   // 2 min — don't refetch on tab focus
    gcTime: 5 * 60 * 1000,      // keep pages in memory 5 min for back-navigation
  });
}

/** Single vacancy. Key: ["jobs","detail",uid,lang]. */
export function useJobDetail(uid: string) {
  const lang = useLang();
  return useQuery({
    queryKey: ["jobs", "detail", uid, lang],
    queryFn: async () => {
      const { data } = await client.get<VacancyDetailResponse>(`/jobs/${uid}`, { params: { lang } });
      return data;
    },
    enabled: Boolean(uid)
  });
}
