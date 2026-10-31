import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addChannel,
  adminKeys,
  checkChannel,
  deleteChannel,
  listChannels,
  patchChannel,
} from "../../../api/admin";
import type { ChannelCreateBody, ChannelCheckResult } from "../../../api/adminTypes";

/** The gate's channel list — small and flat, so a plain query is enough (no cursor). */
export function useChannelsQuery() {
  return useQuery({
    queryKey: adminKeys.channels(),
    queryFn: listChannels,
    staleTime: 15_000,
  });
}

export function useAddChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ChannelCreateBody) => addChannel(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.channels() });
    },
  });
}

export function useSetChannelEnabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      patchChannel(id, { enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.channels() });
    },
  });
}

export function useDeleteChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteChannel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.channels() });
    },
  });
}

/**
 * `checkChannel` in `src/api/admin.ts` is declared `Promise<Channel>`, but the
 * live endpoint (`webapp/routers/admin_channels.py:check_channel`, confirmed by
 * reading the router source) returns `{id, ok, status, detail}` — the
 * `ChannelCheckResult` shape that already exists in `adminTypes.ts`, not a
 * `Channel` row. Since `src/api/*` is owned by the GATE agent, this hook casts
 * at the one call site instead of editing the shared client; see the report.
 */
export function useCheckChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await checkChannel(id)) as unknown as ChannelCheckResult,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.channels() });
    },
  });
}
