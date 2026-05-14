import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

import client from "../api/client";
import type { VacancyDetail, VacancyItem } from "../types";

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

export function useJobs(params: JobsParams) {
  return useInfiniteQuery<JobsPage>({
    queryKey: ["jobs", params],
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

export function useJobDetail(uid: string) {
  return useQuery({
    queryKey: ["jobs", "detail", uid],
    queryFn: async () => {
      const { data } = await client.get<VacancyDetail>(`/jobs/${uid}`);
      return data;
    },
    enabled: Boolean(uid)
  });
}
