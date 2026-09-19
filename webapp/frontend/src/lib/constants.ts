/** Telegram username of the bot this Mini App belongs to (no leading @). */
export const BOT_USERNAME: string =
  import.meta.env.VITE_BOT_USERNAME || "bandlikuzbot";

/** Telegram username used for manual balance top-ups (no leading @). */
export const ADMIN_USERNAME = "UnitedAgency";

/** Free-plan cap on saved vacancies — mirrors `FREE_SAVE_LIMIT` in the API. */
export const FREE_SAVE_LIMIT = 5;

/** `https://t.me/<bot>?start=<param>` */
export function botDeepLink(startParam?: string): string {
  const base = `https://t.me/${BOT_USERNAME}`;
  return startParam ? `${base}?start=${encodeURIComponent(startParam)}` : base;
}

/** Open a t.me link through Telegram when available, otherwise a new tab. */
export function openTelegramLink(url: string): void {
  const tg = window.Telegram?.WebApp;
  if (tg?.openTelegramLink) tg.openTelegramLink(url);
  else window.open(url, "_blank", "noopener,noreferrer");
}
