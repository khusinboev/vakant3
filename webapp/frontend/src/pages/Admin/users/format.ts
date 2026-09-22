import type { TranslationKey } from "../../../i18n";
import type { AdminUserListItem } from "../../../api/adminTypes";

/** "Ism" / "@username" / "#id" — a row is never blank. */
export function displayName(
  user: Pick<AdminUserListItem, "user_id" | "first_name" | "username">,
): string {
  if (user.first_name) return user.first_name;
  if (user.username) return `@${user.username}`;
  return `#${user.user_id}`;
}

export function usernameLine(user: Pick<AdminUserListItem, "user_id" | "username">): string {
  return user.username ? `@${user.username} · ${user.user_id}` : `${user.user_id}`;
}

const LANG_KEY: Record<string, TranslationKey> = {
  uz: "adminUsers.lang.uz",
  ru: "adminUsers.lang.ru",
  en: "adminUsers.lang.en",
};

export function langLabelKey(lang: string | null | undefined): TranslationKey | null {
  return lang ? (LANG_KEY[lang] ?? null) : null;
}

/** `YYYY-MM-DD` -> unix seconds at the start of that local day (undefined when empty). */
export function dayStart(value: string | undefined): number | undefined {
  if (!value) return undefined;
  const ms = new Date(`${value}T00:00:00`).getTime();
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

/** `YYYY-MM-DD` -> unix seconds at the last second of that local day. */
export function dayEnd(value: string | undefined): number | undefined {
  const start = dayStart(value);
  return start === undefined ? undefined : start + 24 * 60 * 60 - 1;
}

/** A signed amount the way the ledger reads it: "+10 000" / "−10 000". */
export function signedAmount(amount: number, formatted: string): string {
  return amount > 0 ? `+${formatted}` : formatted;
}

/** A Telegram id is a positive integer; anything else is a typo, not a request. */
export function parseUserId(raw: string): number | null {
  const value = Number(raw.trim());
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

/** `/admin/users/:id` — the detail screen is a real route (spec §2). */
export function userDetailPath(userId: number): string {
  return `/admin/users/${userId}`;
}

/** `/admin/users/:id/action/:action` — one history entry per action sheet. */
export function userActionPath(userId: number, action: string): string {
  return `/admin/users/${userId}/action/${action}`;
}

/** The five per-user actions, each one a `/action/:action` sub-route. */
export const USER_ACTIONS = ["pro", "balance", "ban", "message", "reset"] as const;

export type UserAction = (typeof USER_ACTIONS)[number];

export function isUserAction(value: string | undefined): value is UserAction {
  return USER_ACTIONS.includes((value ?? "") as UserAction);
}
