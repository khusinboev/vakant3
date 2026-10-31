/**
 * Entry gate: `/api/auth/gate` (bot-start + subscription + referral + role in
 * one call) and its recheck. Typed against the real implementation
 * (`webapp/routers/auth.py:entry_gate_state`, `webapp/core/entry_gate.py:evaluate_entry`,
 * `webapp/core/subscription.py:channel_public`).
 */
import client from "./client";
import type { AdminRole } from "./adminTypes";

export type GateMissingChannel = {
  id: string;
  title: string | null;
  username: string | null;
  invite_link: string | null;
};

export type GateReferralState = {
  enabled: boolean;
  required: number;
  count: number;
  unlocked: boolean;
};

export type GateState = {
  bot_started: boolean;
  subscribed: boolean;
  banned: boolean;
  channels: GateMissingChannel[];
  referral: GateReferralState;
  is_admin: boolean;
  role: AdminRole | null;
};

/** Query key for `useQuery`/`useSuspenseQuery` reads of the gate state. */
export const gateKeys = {
  gate: ["auth", "gate"] as const,
};

/** `GET /api/auth/gate` — the single source of truth for the entry-lock screen and admin role. */
export async function getGate(): Promise<GateState> {
  return (await client.get<GateState>("/auth/gate")).data;
}

/** `POST /api/auth/gate/recheck` (rate limited 6/min) — clears the subscription cache and re-evaluates. */
export async function recheckGate(): Promise<GateState> {
  return (await client.post<GateState>("/auth/gate/recheck")).data;
}
