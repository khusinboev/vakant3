import client from "../../../api/client";
import type { PostNowBody, PostNowResult } from "../../../api/adminTypes";

/**
 * `postAutoPostNow` in `src/api/admin.ts` mints its own confirmation token
 * internally (`withConfirm`), which doesn't fit `useConfirmedMutation`'s
 * `mutationFn: (body, token) => Promise<R>` contract — that hook already
 * mints a token itself (from the dialog's params) and hands it here. Calling
 * the shared helper would mint a second, unused token on every post. This
 * small local fetcher posts with the token `useConfirmedMutation` already
 * has instead.
 */
export async function postAutoPostNowWithToken(body: PostNowBody, token: string): Promise<PostNowResult> {
  return (
    await client.post<PostNowResult>("/admin/auto-post/post-now", body, {
      headers: { "X-Confirm-Token": token },
    })
  ).data;
}
