import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import client from "../api/client";
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
 * Key: ["jobs","list",params] — namespaced so optimistic save patches never
 * touch ["jobs","detail",uid], which holds a completely different shape.
 */
export function useJobs(params: JobsParams) {
  return useInfiniteQuery<JobsPage>({
    queryKey: [...JOBS_LIST_KEY, params],
    queryFn: async ({ pageParam = 1 }) => {
      const { data } = await client.get<JobsPage>("/jobs/search", {
        params: { ...params, page: pageParam },
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

/** Single vacancy. Key: ["jobs","detail",uid]. */
export function useJobDetail(uid: string) {
  return useQuery({
    queryKey: ["jobs", "detail", uid],
    queryFn: async () => {
      const { data } = await client.get<VacancyDetailResponse>(`/jobs/${uid}`);
      return data;
    },
    enabled: Boolean(uid)
  });
}
