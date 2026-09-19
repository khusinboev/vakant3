import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import client from "../../api/client";
import type {
  AddBalanceResult,
  AdminState,
  AdminStatePatch,
  AutoPostSchedule,
  ResetUserResult,
  ResumeDiagnostics,
  ResumeFunnel,
  ResumeGoals,
  ResumeMetrics,
  ResumeUserInspect,
} from "./types";

/**
 * Every admin query lives here so the tabs stay presentational.
 *
 * `retry: false` everywhere on purpose: a non-admin gets 403 and retrying
 * would only hammer the API. Each caller renders the error instead of
 * failing silently (which is what the old single-file page did).
 */

export const adminKeys = {
  state: ["admin", "state"] as const,
  schedule: ["admin", "auto-post-schedule"] as const,
  metrics: ["admin", "resume-metrics"] as const,
  funnel: ["admin", "resume-funnel"] as const,
  diagnostics: ["admin", "resume-diagnostics"] as const,
  goals: ["admin", "resume-goals"] as const,
};

export function useAdminState() {
  return useQuery<AdminState>({
    queryKey: adminKeys.state,
    queryFn: async () => (await client.get<AdminState>("/admin/state")).data,
    retry: false,
  });
}

export function useAutoPostSchedule() {
  return useQuery<AutoPostSchedule>({
    queryKey: adminKeys.schedule,
    queryFn: async () => (await client.get<AutoPostSchedule>("/admin/auto-post-schedule")).data,
    refetchInterval: 60_000,
    retry: false,
  });
}

export function useResumeMetrics() {
  return useQuery<ResumeMetrics>({
    queryKey: adminKeys.metrics,
    queryFn: async () => (await client.get<ResumeMetrics>("/admin/resume-metrics")).data,
    retry: false,
  });
}

export function useResumeFunnel() {
  return useQuery<ResumeFunnel>({
    queryKey: adminKeys.funnel,
    queryFn: async () => (await client.get<ResumeFunnel>("/admin/resume-funnel")).data,
    retry: false,
  });
}

export function useResumeDiagnostics() {
  return useQuery<ResumeDiagnostics>({
    queryKey: adminKeys.diagnostics,
    queryFn: async () => (await client.get<ResumeDiagnostics>("/admin/resume-diagnostics")).data,
    retry: false,
  });
}

export function useResumeGoals() {
  return useQuery<ResumeGoals>({
    queryKey: adminKeys.goals,
    queryFn: async () => (await client.get<ResumeGoals>("/admin/resume-goals")).data,
    retry: false,
  });
}

/** `PATCH /admin/state` — the response is the full new state, so it seeds the cache. */
export function useAdminStatePatch() {
  const queryClient = useQueryClient();
  return useMutation<AdminState, unknown, AdminStatePatch>({
    mutationFn: async (payload) => (await client.patch<AdminState>("/admin/state", payload)).data,
    onSuccess: (data) => {
      queryClient.setQueryData(adminKeys.state, data);
      // The KPI donuts read the targets that were just changed.
      void queryClient.invalidateQueries({ queryKey: adminKeys.goals });
    },
  });
}

export function useAddBalance() {
  return useMutation<AddBalanceResult, unknown, { userId: number; amount: number }>({
    mutationFn: async ({ userId, amount }) =>
      (
        await client.post<AddBalanceResult>("/wallet/admin/add-balance", {
          user_id: userId,
          amount,
        })
      ).data,
  });
}

export function useResetUser() {
  return useMutation<ResetUserResult, unknown, number>({
    mutationFn: async (userId) =>
      (await client.post<ResetUserResult>("/wallet/admin/reset-user", { user_id: userId })).data,
  });
}

export function useInspectResumeUser() {
  return useMutation<ResumeUserInspect, unknown, number>({
    mutationFn: async (userId) =>
      (await client.get<ResumeUserInspect>(`/admin/resume-user/${userId}`)).data,
  });
}
