/**
 * The requests the Users page needs that `src/api/admin.ts` cannot express.
 *
 * `setUserBalance` / `adminResetUser` mint their own confirmation token and
 * take no token argument, while `useConfirmedMutation` mints the token itself
 * and hands it to `mutationFn` — these two wrappers are the same requests with
 * the token injected. `getResumeInspect` is the resume snapshot the old
 * "Quick actions" tab showed (CONTRACT_UI: pages must not edit `src/api/*`).
 */
import client from "../../../api/client";
import type {
  AdminAddBalanceResponse,
  AdminResetUserResponse,
  AdminUserBalanceBody,
} from "../../../api/adminTypes";
import type { ResumeUserInspect } from "../types";

export type ConfirmHeaders = { headers: { "X-Confirm-Token": string } };

const withToken = (token: string): ConfirmHeaders => ({ headers: { "X-Confirm-Token": token } });

/** `POST /admin/users/{id}/balance` — confirmation action `users.balance`. */
export async function postUserBalance(
  userId: number,
  body: AdminUserBalanceBody,
  token: string,
): Promise<AdminAddBalanceResponse> {
  const { data } = await client.post<AdminAddBalanceResponse>(
    `/admin/users/${userId}/balance`,
    body,
    withToken(token),
  );
  return data;
}

/** `POST /wallet/admin/reset-user` — confirmation action `wallet.reset_user`. */
export async function postResetUser(
  userId: number,
  note: string | undefined,
  token: string,
): Promise<AdminResetUserResponse> {
  const { data } = await client.post<AdminResetUserResponse>(
    "/wallet/admin/reset-user",
    { user_id: userId, note },
    withToken(token),
  );
  return data;
}

/** `GET /admin/resume-user/{id}` — resume state, template and recent events. */
export async function getResumeInspect(userId: number): Promise<ResumeUserInspect> {
  const { data } = await client.get<ResumeUserInspect>(`/admin/resume-user/${userId}`);
  return data;
}
