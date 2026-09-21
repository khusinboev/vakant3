import type { TranslationKey } from "../../../i18n";
import type { AdminUserListItem } from "../../../api/adminTypes";

/** "Ism (@username)" — falls back to the bare id so a row is never blank. */
export function displayName(user: Pick<AdminUserListItem, "user_id" | "first_name" | "username">): string {
  if (user.first_name) return user.first_name;
  if (user.username) return `@${user.username}`;
  return `#${user.user_id}`;
}

export function usernameLine(
  user: Pick<AdminUserListItem, "user_id" | "username">,
): string {
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
export function dayStart(value: string): number | undefined {
  if (!value) return undefined;
  const ms = new Date(`${value}T00:00:00`).getTime();
  return Number.isNaN(ms) ? undefined : Math.floor(ms / 1000);
}

/** `YYYY-MM-DD` -> unix seconds at the last second of that local day. */
export function dayEnd(value: string): number | undefined {
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
