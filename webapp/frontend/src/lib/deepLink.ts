/**
 * Mini App entry deep links.
 *
 * The bot opens the app with `?go=<value>` (inline `web_app` buttons) or a
 * Telegram `start_param` (`t.me/<bot>/<app>?startapp=<value>`). Both carry the
 * same values: `profile`, `saves`, `home`/`app`/`jobs`, or
 * `vacancy_osonish_<id>` (Telegram allows only `[A-Za-z0-9_-]`, max 64 chars).
 */

export type EntryTarget =
  | { kind: "home" }
  | { kind: "profile" }
  | { kind: "saves" }
  | { kind: "vacancy"; uid: string };

/** Query key Home uses for the open vacancy sheet: `/app?vacancy=osonish_<id>`. */
export const VACANCY_QUERY_KEY = "vacancy";

const VACANCY_UID_RE = /^osonish_\d{1,15}$/;
const VACANCY_ENTRY_RE = /^vacancy_(osonish_\d{1,15})$/;

/** True for a vacancy uid the API accepts (guards the `/jobs/<uid>` path). */
export function isVacancyUid(value: string): boolean {
  return VACANCY_UID_RE.test(value);
}

function parseEntryValue(raw: string): EntryTarget | null {
  const value = raw.trim().toLowerCase();
  if (!value) return null;
  if (value === "profile") return { kind: "profile" };
  if (value === "saves") return { kind: "saves" };
  if (value === "home" || value === "app" || value === "jobs") return { kind: "home" };
  const match = VACANCY_ENTRY_RE.exec(value);
  if (match) return { kind: "vacancy", uid: match[1] };
  return null;
}

// Telegram keeps `start_param` in initData for the whole session, so it must
// act only on the first visit of `/app`: otherwise every later tap on "Home"
// would redirect (or reopen the vacancy) again.
let startParamConsumed = false;

/** Mark the session's `start_param` as handled (call after acting on it). */
export function consumeStartParam(): void {
  startParamConsumed = true;
}

/** `?go=` wins (it is in this URL only); then an unconsumed `start_param`. */
export function resolveEntryTarget(search: string): EntryTarget {
  const fromGo = parseEntryValue(new URLSearchParams(search).get("go") || "");
  if (fromGo) return fromGo;
  if (!startParamConsumed) {
    const fromStart = parseEntryValue(window.Telegram?.WebApp?.initDataUnsafe?.start_param || "");
    if (fromStart) return fromStart;
  }
  return { kind: "home" };
}
