/**
 * Local fetchers for the two confirmed (token-carrying) user actions.
 *
 * `src/api/admin.ts` exposes `setUserBalance` / `adminResetUser`, but both mint
 * their own confirmation token internally and take no token argument, while
 * `useConfirmedMutation` mints the token itself and hands it to `mutationFn`.
 * These two wrappers are the same requests with the token injected — nothing
 * else lives here (see CONTRACT_UI: pages must not edit `src/api/*`).
 */
import client from "../../../api/client";
import type {
  AdminAddBalanceResponse,
  AdminResetUserResponse,
  AdminUserBalanceBody,
} from "../../../api/adminTypes";

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
