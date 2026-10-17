/**
 * The entry-gate verdict the API returns from `GET /api/auth/gate`.
 * The server enforces it on every gated endpoint (webapp/core/entry_gate.py);
 * the Mini App only decides which screen to render.
 */
export type GateChannel = {
  id: string;
  title: string | null;
  username: string | null;
  invite_link: string | null;
};

export type GateState = {
  bot_started: boolean;
  subscribed: boolean;
  banned: boolean;
  channels: GateChannel[];
  referral: { enabled: boolean; required: number; count: number; unlocked: boolean };
  is_admin: boolean;
  role: string | null;
};

export type GateBlockReason = "banned" | "bot_start" | "subscribe" | "referral";

/**
 * Which wall the user is behind, in the server's own order.
 * `null` means the user is allowed in.
 */
export function gateBlockReason(gate: GateState | undefined): GateBlockReason | null {
  if (!gate || gate.is_admin) return null;
  if (gate.banned) return "banned";
  if (!gate.bot_started) return "bot_start";
  if (!gate.subscribed) return "subscribe";
  if (gate.referral.enabled && !gate.referral.unlocked) return "referral";
  return null;
}
