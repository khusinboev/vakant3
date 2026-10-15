/**
 * The requests the Users page needs that `src/api/admin.ts` cannot express.
 *
 * `useConfirmedMutation` mints the confirmation token itself and hands it to
 * `mutationFn`, so the confirmed requests here take the token as an argument.
 * Types the shared `adminTypes.ts` does not describe (yet) are page-local:
 * the detail's `target_role`/`actionable`, the reset/revoke results and the
 * CSV export. `getResumeInspect` is the resume snapshot the old "Quick
 * actions" tab showed (CONTRACT_UI: pages must not edit `src/api/*`).
 */
import client from "../../../api/client";
import type {
  AdminUserBalanceBody,
  AdminUserBalanceResult,
  AdminUserDetail,
  AdminUsersQuery,
} from "../../../api/adminTypes";
import type { AdminRole } from "../hooks/useAdminRole";
import type { ResumeUserInspect } from "../types";

export type ConfirmHeaders = { headers: Record<string, string> };

const withToken = (token: string, extra: Record<string, string> = {}): ConfirmHeaders => ({
  headers: { "X-Confirm-Token": token, ...extra },
});

/** What `GET /admin/users/{id}` adds on top of `AdminUserDetail`. */
export type UserDetailWithRole = AdminUserDetail & {
  /** The admin role the user holds; `null` for a regular user. */
  target_role?: AdminRole | null;
  /** `false` when the user's role ranks at or above the viewer's: every action is refused. */
  actionable?: boolean;
};

/** A UUID v4 for `X-Idempotency-Key` (crypto.randomUUID needs a secure context). */
export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * `POST /admin/users/{id}/balance` — confirmation action `users.balance`,
 * param keys `[user_id, amount]`. The backend `BalanceRequest` requires
 * `user_id` in the body (it must equal the path id) and the token MAC is
 * recomputed from the body's `user_id`/`amount`, so both travel in the body.
 *
 * `idempotencyKey` is fresh per submission and reused when that same
 * submission is retried: the server then replays the first result instead of
 * moving the money twice.
 */
export async function postUserBalance(
  userId: number,
  body: AdminUserBalanceBody,
  token: string,
  idempotencyKey: string,
): Promise<AdminUserBalanceResult> {
  const { data } = await client.post<AdminUserBalanceResult>(
    `/admin/users/${userId}/balance`,
    { user_id: userId, amount: body.amount, note: body.note },
    withToken(token, { "X-Idempotency-Key": idempotencyKey }),
  );
  return data;
}

export type ResetUserResult = {
  ok: boolean;
  user_id: number;
  amount: number;
  new_balance: number;
  tx_id: number;
};

/** `POST /admin/users/{id}/reset` — confirmation action `users.reset`, param keys `[user_id]`. */
export async function postResetUser(
  userId: number,
  note: string | undefined,
  token: string,
): Promise<ResetUserResult> {
  const { data } = await client.post<ResetUserResult>(
    `/admin/users/${userId}/reset`,
    { user_id: userId, note },
    withToken(token),
  );
  return data;
}

export type RevokeSessionsResult = { ok: boolean; user_id: number; revoked: number };

/** `POST /admin/users/{id}/sessions/revoke` — action `users.sessions_revoke`, param keys `[user_id]`. */
export async function postRevokeSessions(userId: number, token: string): Promise<RevokeSessionsResult> {
  const { data } = await client.post<RevokeSessionsResult>(
    `/admin/users/${userId}/sessions/revoke`,
    { user_id: userId },
    withToken(token),
  );
  return data;
}

/** `GET /admin/resume-user/{id}` — resume state, template and recent events. */
export async function getResumeInspect(userId: number): Promise<ResumeUserInspect> {
  const { data } = await client.get<ResumeUserInspect>(`/admin/resume-user/${userId}`);
  return data;
}

// ── CSV export ───────────────────────────────────────────────────────────────

/** The export's filters exactly as the server canonicalises them. */
export type ExportParams = Record<string, string | number | boolean>;

/**
 * The list query reduced to what `/export.csv` takes, in the server's
 * canonical form (`canonical_export_filters`): `sort` always, every other
 * filter only when set, `q` trimmed, booleans and numbers as real JSON types.
 * A download-link token is signed over this dict, so it must match byte for
 * byte after JSON canonicalisation.
 */
export function exportParams(query: AdminUsersQuery): ExportParams {
  const params: ExportParams = { sort: query.sort ?? "date" };
  const q = query.q?.trim();
  if (q) params.q = q;
  if (query.pro !== undefined) params.pro = query.pro;
  if (query.banned !== undefined) params.banned = query.banned;
  if (query.blocked !== undefined) params.blocked = query.blocked;
  if (query.lang) params.lang = query.lang;
  if (query.region) params.region = query.region;
  if (query.from !== undefined) params.from = query.from;
  if (query.to !== undefined) params.to = query.to;
  return params;
}

export type CsvExport = { blob: Blob; rows: number; truncated: boolean };

/**
 * With `responseType: "blob"` an error body is a Blob too, which would hide
 * the API's `{detail: {code}}` from `parseApiError` — decode it back to JSON.
 */
async function decodeBlobError(error: unknown): Promise<never> {
  const response = (error as { response?: { data?: unknown } })?.response;
  if (response && response.data instanceof Blob) {
    try {
      response.data = JSON.parse(await response.data.text());
    } catch {
      response.data = undefined;
    }
  }
  throw error;
}

/** `GET /admin/users/export.csv` through the authenticated client (Bearer). */
export async function fetchUsersCsv(params: ExportParams): Promise<CsvExport> {
  try {
    const response = await client.get<Blob>("/admin/users/export.csv", {
      params,
      responseType: "blob",
    });
    return {
      blob: response.data,
      rows: Number(response.headers["x-export-rows"] ?? 0),
      truncated: response.headers["x-export-truncated"] === "1",
    };
  } catch (error) {
    return decodeBlobError(error);
  }
}

/**
 * Absolute URL of the single-use link `/export/download.csv` for
 * `Telegram.WebApp.downloadFile` (which fetches it without our headers).
 * `token` is a `users.export_download` confirmation token over `params`.
 */
export function usersCsvDownloadUrl(params: ExportParams, actorId: number, token: string): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) search.set(key, String(value));
  search.set("actor", String(actorId));
  search.set("dl", token);
  const base = client.defaults.baseURL ?? "/api";
  return new URL(`${base}/admin/users/export/download.csv?${search}`, window.location.origin).toString();
}
