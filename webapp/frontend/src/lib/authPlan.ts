/**
 * Which identity signs the Mini App in on this launch — a pure decision, so
 * `scripts/auth-check.mjs` can test it without a browser. No imports.
 *
 * Owner rule: the app always opens as the CURRENT Telegram account, with no
 * confirmation prompt, and a session cached on this device for another
 * account is never used.
 *
 *  1. Non-empty initData (inline / menu / startapp / attachment launches):
 *     reuse the stored session only when it is recorded for the very user in
 *     `initDataUnsafe.user.id`; otherwise drop it and log in with initData.
 *  2. Else a signed `bt` link (reply-keyboard button, empty initData): always
 *     exchange it and replace whatever is stored. A stored session of the
 *     link's (unverified) owner is kept aside only as a fallback for a failed
 *     exchange — it is that same user's own session either way.
 *  3. Else (a reload after `bt` left the URL, or no identity at all): reuse the
 *     stored session if the API still accepts it.
 */

export type StoredSession = { token: string; userId: number | null };

export type AuthBootInput = {
  /** `Telegram.WebApp.initData` is non-empty. */
  hasInitData: boolean;
  /** `initDataUnsafe.user.id`, when Telegram gave one. */
  initDataUserId: number | null;
  /** The well-formed `bt` captured from the URL, if any. */
  botLink: string | null;
  /** The user id inside that link, UNVERIFIED (the server checks the MAC). */
  botLinkUserId: number | null;
  stored: StoredSession | null;
};

export type AuthBootPlan =
  /** initData user = stored user: keep the session. */
  | { kind: "reuse" }
  /** Log in with initData; `clearStored` = drop the stored session first. */
  | { kind: "initData"; clearStored: boolean }
  /** Exchange the link; `fallback` = stored session to restore if it fails. */
  | { kind: "botLink"; clearStored: boolean; fallback: StoredSession | null }
  /** No identity source: validate and reuse the stored session. */
  | { kind: "restore" }
  /** Nothing to sign in with yet (initData may still arrive). */
  | { kind: "none" };

function validId(id: number | null | undefined): id is number {
  return typeof id === "number" && Number.isSafeInteger(id) && id > 0;
}

export function planAuthBoot(input: AuthBootInput): AuthBootPlan {
  const { stored } = input;
  if (input.hasInitData) {
    const same =
      stored !== null &&
      validId(stored.userId) &&
      validId(input.initDataUserId) &&
      stored.userId === input.initDataUserId;
    return same ? { kind: "reuse" } : { kind: "initData", clearStored: stored !== null };
  }
  if (input.botLink) {
    const fallback =
      stored !== null && validId(stored.userId) && stored.userId === input.botLinkUserId ? stored : null;
    return { kind: "botLink", clearStored: stored !== null, fallback };
  }
  return stored ? { kind: "restore" } : { kind: "none" };
}

/** True when a login replaced a session that belonged to someone else. */
export function isAccountSwitch(previousUserId: number | null, nextUserId: number): boolean {
  return validId(previousUserId) && previousUserId !== nextUserId;
}

/** Prefixes of localStorage keys scoped `<prefix>:<userId>` (resume drafts). */
export const USER_SCOPED_KEY_PREFIXES = ["resume_wizard_draft_v2", "resume_wizard_photo_v1"] as const;

/** The localStorage keys that hold `userId`'s private data. */
export function userScopedKeys(allKeys: readonly string[], userId: number): string[] {
  if (!validId(userId)) return [];
  const wanted = new Set(USER_SCOPED_KEY_PREFIXES.map((prefix) => `${prefix}:${userId}`));
  return allKeys.filter((key) => wanted.has(key));
}
