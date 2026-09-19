import {
  InfiniteData,
  QueryKey,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";

import client from "../api/client";
import { parseApiError } from "../lib/parseApiError";
import type { VacancyItem } from "../types";

type JobsPage = { vacancies: VacancyItem[]; page: number; last_page: number; total_estimate: number };

/** Query key of the infinite job list, kept next to the patcher that walks it. */
export const JOBS_LIST_KEY = ["jobs", "list"] as const;

type Snapshot = [QueryKey, InfiniteData<JobsPage> | undefined];

/**
 * Optimistically flips `is_saved` in every cached job-list page and returns the
 * previous values keyed by query key, so a rollback restores exactly what it
 * replaced (restoring by index across an unstable query set corrupted caches).
 * Only ["jobs","list",…] is touched — ["jobs","detail",uid] has another shape.
 */
function patchInfiniteJobs(
  queryClient: ReturnType<typeof useQueryClient>,
  uid: string,
  is_saved: boolean,
): Snapshot[] {
  const listQueries = queryClient.getQueriesData<InfiniteData<JobsPage>>({
    queryKey: JOBS_LIST_KEY,
  });
  const snapshots: Snapshot[] = [];

  for (const [key, value] of listQueries) {
    if (!value?.pages) continue;
    snapshots.push([key, value]);
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

function rollback(
  queryClient: ReturnType<typeof useQueryClient>,
  snapshots: Snapshot[] | undefined,
) {
  if (!snapshots) return;
  for (const [key, value] of snapshots) {
    queryClient.setQueryData(key, value);
  }
}

export function useSaves(page = 1, limit = 10, enabled = true) {
  const queryClient = useQueryClient();
  const [saveLimitReached, setSaveLimitReached] = useState(false);

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
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
  });

  const save = useMutation({
    mutationFn: async (uid: string) => client.post(`/saves/${uid}`),
    onMutate: async (uid: string) => {
      await queryClient.cancelQueries({ queryKey: JOBS_LIST_KEY });
      return { snapshots: patchInfiniteJobs(queryClient, uid, true), uid };
    },
    onError: (error, _uid, context) => {
      rollback(queryClient, context?.snapshots);
      if (parseApiError(error).code === "SAVE_LIMIT_REACHED") setSaveLimitReached(true);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["saves"] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  const remove = useMutation({
    mutationFn: async (uid: string) => client.delete(`/saves/${uid}`),
    onMutate: async (uid: string) => {
      await queryClient.cancelQueries({ queryKey: JOBS_LIST_KEY });
      return { snapshots: patchInfiniteJobs(queryClient, uid, false), uid };
    },
    onError: (_error, _uid, context) => {
      rollback(queryClient, context?.snapshots);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["saves"] });
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  return { list, save, remove, saveLimitReached, clearSaveLimitReached: () => setSaveLimitReached(false) };
}
