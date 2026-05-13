import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import client from "../api/client";
import type { VacancyItem } from "../types";

export function useSaves(page = 1, limit = 10) {
  const queryClient = useQueryClient();

  const list = useQuery({
    queryKey: ["saves", page, limit],
    queryFn: async () => {
      const { data } = await client.get<{ items: Array<{ uid: string; data: Record<string, unknown> }>; total: number }>(
        "/saves",
        { params: { page, limit } }
      );
      return data;
    }
  });

  const save = useMutation({
    mutationFn: async (uid: string) => client.post(`/saves/${uid}`),
    onMutate: async (uid: string) => {
      await queryClient.cancelQueries({ queryKey: ["jobs"] });
      const previousJobs = queryClient.getQueriesData<{ vacancies: VacancyItem[] } | undefined>({ queryKey: ["jobs"] });

      for (const [key, value] of previousJobs) {
        if (!value?.vacancies) continue;
        queryClient.setQueryData(key, {
          ...value,
          vacancies: value.vacancies.map((v) => (v.uid === uid ? { ...v, is_saved: true } : v)),
        });
      }

      return { previousJobs };
    },
    onError: (_err, _uid, context) => {
      if (!context?.previousJobs) return;
      for (const [key, value] of context.previousJobs) {
        queryClient.setQueryData(key, value);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saves"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    }
  });

  const remove = useMutation({
    mutationFn: async (uid: string) => client.delete(`/saves/${uid}`),
    onMutate: async (uid: string) => {
      await queryClient.cancelQueries({ queryKey: ["jobs"] });
      const previousJobs = queryClient.getQueriesData<{ vacancies: VacancyItem[] } | undefined>({ queryKey: ["jobs"] });

      for (const [key, value] of previousJobs) {
        if (!value?.vacancies) continue;
        queryClient.setQueryData(key, {
          ...value,
          vacancies: value.vacancies.map((v) => (v.uid === uid ? { ...v, is_saved: false } : v)),
        });
      }

      return { previousJobs };
    },
    onError: (_err, _uid, context) => {
      if (!context?.previousJobs) return;
      for (const [key, value] of context.previousJobs) {
        queryClient.setQueryData(key, value);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saves"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    }
  });

  return { list, save, remove };
}
