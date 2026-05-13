import { keepPreviousData, useQuery } from "@tanstack/react-query";

import client from "../api/client";
import type { VacancyDetail, VacancyItem } from "../types";

export type JobsParams = {
  page: number;
  money: number;
  region_soato: string;
  district_soato: string;
  specs: string;
  sort_key: string;
  sort_type: string;
};

export function useJobs(params: JobsParams) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: async () => {
      const { data } = await client.get<{ vacancies: VacancyItem[]; page: number; last_page: number; total_estimate: number }>(
        "/jobs/search",
        { params }
      );
      return data;
    },
    placeholderData: keepPreviousData
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
