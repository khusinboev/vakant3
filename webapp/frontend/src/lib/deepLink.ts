/**
 * Mini App entry deep links.
 *
 * The bot opens the app with `?go=<value>` (inline `web_app` buttons) or a
 * Telegram `start_param` (`t.me/<bot>/<app>?startapp=<value>`). Both carry the
 * same values: `profile`, `saves`, `home`/`app`/`jobs`, or a vacancy: the
 * opaque token `v<source letter><id in base36>` (hides the source; mirror of
 * `src/functions/vacancy_token.py`) or the legacy `vacancy_<source>_<id>` that
 * already-posted messages carry. Telegram allows only `[A-Za-z0-9_-]`, max 64
 * chars.
 */

export type EntryTarget =
  | { kind: "home" }
  | { kind: "profile" }
  | { kind: "saves" }
  | { kind: "vacancy"; uid: string };

/** Query key Home uses for the open vacancy sheet: `/app?vacancy=<token>` (legacy `<source>_<id>` still read). */
export const VACANCY_QUERY_KEY = "vacancy";

// Same shape the API accepts (`src/functions/vacancy_format.py` _STORE_UID_RE).
const VACANCY_UID_RE = /^(osonish|hh|vacancy_gov)_[1-9]\d{0,14}$/;
const VACANCY_ENTRY_RE = /^vacancy_((?:osonish|hh|vacancy_gov)_[1-9]\d{0,14})$/;
const VACANCY_TOKEN_RE = /^v([hog])([0-9a-z]{1,14})$/;
const SOURCE_CODES: Record<string, string> = { hh: "h", osonish: "o", vacancy_gov: "g" };
const CODE_SOURCES: Record<string, string> = { h: "hh", o: "osonish", g: "vacancy_gov" };

/** `hh_138492163` -> `vh2a3f9k` (BigInt: ids reach 16 digits, past 2^53). */
export function vacancyToken(uid: string): string | null {
  const match = /^(osonish|hh|vacancy_gov)_([1-9]\d{0,14})$/.exec(uid);
  return match ? `v${SOURCE_CODES[match[1]]}${BigInt(match[2]).toString(36)}` : null;
}

export function uidFromToken(value: string): string | null {
  const match = VACANCY_TOKEN_RE.exec(value);
  const source = match ? CODE_SOURCES[match[1]] : undefined;
  if (!match || !source) return null;
  let id = 0n;
  for (const ch of match[2]) id = id * 36n + BigInt(parseInt(ch, 36));
  const uid = `${source}_${id}`;
  return VACANCY_UID_RE.test(uid) ? uid : null;
}

/** uid of a `?vacancy=` value: the opaque token, or an old-style uid. `""` when neither. */
export function vacancyUidFromQuery(value: string): string {
  const v = value.trim().toLowerCase();
  return isVacancyUid(v) ? v : uidFromToken(v) ?? "";
}

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
  const tokenUid = uidFromToken(value);
  if (tokenUid) return { kind: "vacancy", uid: tokenUid };
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
