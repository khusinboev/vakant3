import { getGate, type GateState } from "../../../api/gate";
import client from "../../../api/client";
import { parseApiError } from "../../../lib/parseApiError";
import type { AdminRole } from "../../../api/adminTypes";

export type { AdminRole, GateState };
export type GateInfo = GateState;

/** Roles ordered weakest -> strongest (mirrors `ROLES` in webapp/core/auth.py). */
export const ADMIN_ROLES = ["viewer", "moderator", "admin", "owner"] as const;

function normalizeRole(value: unknown, isAdmin: boolean): AdminRole | null {
  if (typeof value === "string" && (ADMIN_ROLES as readonly string[]).includes(value)) {
    return value as AdminRole;
  }
  // The gate can be live before the `admins` table is populated: an actor the
  // API still calls "admin" without a role is treated as a full admin.
  return isAdmin ? "admin" : null;
}

const OPEN_GATE = {
  bot_started: true,
  subscribed: true,
  banned: false,
  channels: [],
  referral: { enabled: false, required: 0, count: 0, unlocked: true },
} satisfies Omit<GateState, "is_admin" | "role">;

/**
 * One call for "who am I and may I be here".
 *
 * `/auth/gate` is being added by the entry-gate work; while it is missing this
 * falls back to `GET /admin/state`, which already carries `is_admin` and
 * (after Phase 0) `role`. A 401/403 there simply means "not an admin", which
 * is a valid answer — not an error.
 */
export async function fetchGate(): Promise<GateState> {
  try {
    const data = (await getGate()) as Partial<GateState>;
    return {
      ...OPEN_GATE,
      ...data,
      channels: data.channels ?? [],
      referral: data.referral ?? OPEN_GATE.referral,
      is_admin: Boolean(data.is_admin),
      role: normalizeRole(data.role, Boolean(data.is_admin)),
    };
  } catch (error) {
    const { status } = parseApiError(error);
    if (status !== 404 && status !== 405) throw error;

    try {
      const { data } = await client.get<{ is_admin?: boolean; role?: string }>("/admin/state");
      return {
        ...OPEN_GATE,
        is_admin: Boolean(data.is_admin),
        role: normalizeRole(data.role, Boolean(data.is_admin)),
      };
    } catch (fallbackError) {
      const parsed = parseApiError(fallbackError);
      if (parsed.status === 401 || parsed.status === 403) {
        return { ...OPEN_GATE, is_admin: false, role: null };
      }
      throw fallbackError;
    }
  }
}

export const GATE_QUERY_KEY = ["auth", "gate"] as const;
