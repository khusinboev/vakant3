import { useMemo } from "react";
import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";

import type { TranslationKey } from "../../../i18n";
import {
  ADMIN_ROLES,
  GATE_QUERY_KEY,
  fetchGate,
  type AdminRole,
  type GateInfo,
} from "./gateApi";

export type { AdminRole, GateInfo };
export { ADMIN_ROLES, GATE_QUERY_KEY };

/** `true` when `role` is at least as strong as `min`. */
export function roleAtLeast(role: AdminRole | null | undefined, min: AdminRole): boolean {
  if (!role) return false;
  return ADMIN_ROLES.indexOf(role) >= ADMIN_ROLES.indexOf(min);
}

export const ROLE_LABEL_KEY: Record<AdminRole, TranslationKey> = {
  owner: "admin.role.owner",
  admin: "admin.role.admin",
  moderator: "admin.role.moderator",
  viewer: "admin.role.viewer",
};

/** The shared `["auth","gate"]` query — one request for the whole app. */
export function useGateQuery(): UseQueryResult<GateInfo> {
  return useQuery<GateInfo>({
    queryKey: GATE_QUERY_KEY,
    queryFn: fetchGate,
    retry: false,
    staleTime: 60_000,
  });
}

export type AdminRoleApi = {
  /** `null` for everyone who is not an admin (and while the gate is loading). */
  role: AdminRole | null;
  isAdmin: boolean;
  /** `atLeast("admin")` — the single check every RoleGate / page uses. */
  atLeast: (min: AdminRole) => boolean;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
};

export function useAdminRole(): AdminRoleApi {
  const query = useGateQuery();
  const role = query.data?.role ?? null;
  const refetch = query.refetch;

  return useMemo(
    () => ({
      role,
      isAdmin: Boolean(query.data?.is_admin),
      atLeast: (min: AdminRole) => roleAtLeast(role, min),
      isLoading: query.isLoading,
      error: query.isError ? query.error : null,
      refetch: () => void refetch(),
    }),
    [role, query.data?.is_admin, query.isLoading, query.isError, query.error, refetch],
  );
}

/** Drop the cached gate (after a role change or a subscription re-check). */
export function useInvalidateGate(): () => void {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: GATE_QUERY_KEY });
}

export default useAdminRole;
