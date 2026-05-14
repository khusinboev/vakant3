import { InfiniteData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import client from "../api/client";
import type { VacancyItem } from "../types";

type JobsPage = { vacancies: VacancyItem[]; page: number; last_page: number; total_estimate: number };

function patchInfiniteJobs(
  queryClient: ReturnType<typeof useQueryClient>,
  uid: string,
  is_saved: boolean,
): InfiniteData<JobsPage>[] {
  const allQueries = queryClient.getQueriesData<InfiniteData<JobsPage>>({ queryKey: ["jobs"] });
  const snapshots: InfiniteData<JobsPage>[] = [];

  for (const [key, value] of allQueries) {
    if (!value?.pages) continue;
    snapshots.push(value);
    queryClient.setQueryData<InfiniteData<JobsPage>>(key, {
      ...value,
      pages: value.pages.map((page) => ({
        ...page,
        vacancies: page.vacancies.map((v) => (v.uid === uid ? { ...v, is_saved } : v)),
      })),
    });
  }
  return snapshots;
}

export function useSaves(page = 1, limit = 10, enabled = true) {
  const queryClient = useQueryClient();

  const list = useQuery({
    queryKey: ["saves", page, limit],
    queryFn: async () => {
      const { data } = await client.get<{ items: Array<{ uid: string; data: Record<string, unknown> }>; total: number }>(
        "/saves",
        { params: { page, limit } }
      );
      return data;
    },
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const save = useMutation({
    mutationFn: async (uid: string) => client.post(`/saves/${uid}`),
    onMutate: async (uid: string) => {
      await queryClient.cancelQueries({ queryKey: ["jobs"] });
      const snapshots = patchInfiniteJobs(queryClient, uid, true);
      return { snapshots, uid };
    },
    onError: (_err, _uid, context) => {
      if (!context) return;
      const allQueries = queryClient.getQueriesData<InfiniteData<JobsPage>>({ queryKey: ["jobs"] });
      allQueries.forEach(([key], i) => queryClient.setQueryData(key, context.snapshots[i]));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saves"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  const remove = useMutation({
    mutationFn: async (uid: string) => client.delete(`/saves/${uid}`),
    onMutate: async (uid: string) => {
      await queryClient.cancelQueries({ queryKey: ["jobs"] });
      const snapshots = patchInfiniteJobs(queryClient, uid, false);
      return { snapshots, uid };
    },
    onError: (_err, _uid, context) => {
      if (!context) return;
      const allQueries = queryClient.getQueriesData<InfiniteData<JobsPage>>({ queryKey: ["jobs"] });
      allQueries.forEach(([key], i) => queryClient.setQueryData(key, context.snapshots[i]));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saves"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  return { list, save, remove };
}
