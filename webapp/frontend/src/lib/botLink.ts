/**
 * Bot keyboard links (`?bt=`). A `web_app` button on a REPLY keyboard opens
 * the Mini App with EMPTY initData, so the bot puts a signed personal token in
 * the URL (`src/functions/webapp_link.py`); we exchange it for the normal
 * Bearer session at `POST /api/auth/bot-link`.
 *
 * The token is a credential:
 *  - it is captured once, when this module is evaluated (before React Router
 *    renders or any `?go=` dispatch rewrites the URL), and removed from the
 *    address bar right away with `history.replaceState`, so it is never kept
 *    in the history/back stack nor copied by a "share link";
 *  - a link alone never signs in. Anyone can put our URL with HIS token into
 *    his own bot's keyboard (a genuine Telegram webview with empty initData):
 *    a silent login would put the victim in the attacker's account. The API
 *    answers 409 `BOT_LINK_CONFIRM{name}` and we ask «<name> sifatida
 *    kirasizmi?» first (ported from SlaydX `MiniAppBridge`).
 */
import { createT, ensureDictionary } from "../i18n";
import { currentLang } from "../store/lang";

export const BOT_LINK_PARAM = "bt";
const TOKEN_SHAPE = /^[A-Za-z0-9_-]{39}$/;
/** Survives a reload of the same webview, after `bt` left the URL. */
const KEYBOARD_LAUNCH_KEY = "vk_keyboard_launch";

/** The single well-formed `bt` of a search string, or null (absent, repeated, malformed). */
export function botLinkFromSearch(search: string): string | null {
  try {
    const all = new URLSearchParams(search).getAll(BOT_LINK_PARAM);
    return all.length === 1 && TOKEN_SHAPE.test(all[0]) ? all[0] : null;
  } catch {
    return null;
  }
}

/**
 * The user id inside a version-1 token, UNVERIFIED. Only a UX input («this
 * link is the account already signed in: skip the exchange»); the server
 * verifies the MAC.
 */
export function botLinkUserId(token: string): number | null {
  try {
    if (!TOKEN_SHAPE.test(token)) return null;
    const bin = atob(token.replace(/-/g, "+").replace(/_/g, "/") + "=");
    if (bin.length !== 29 || bin.charCodeAt(0) !== 1) return null;
    const word = (at: number) =>
      ((bin.charCodeAt(at) << 24) >>> 0) +
      (bin.charCodeAt(at + 1) << 16) +
      (bin.charCodeAt(at + 2) << 8) +
      bin.charCodeAt(at + 3);
    const hi = word(1);
    if (hi >= 0x20_0000) return null; // above 2^53 - 1
    const id = hi * 0x1_0000_0000 + word(5);
    return id > 0 ? id : null;
  } catch {
    return null;
  }
}

function removeBotLinkFromUrl(): void {
  try {
    const url = new URL(window.location.href);
    if (!url.searchParams.has(BOT_LINK_PARAM)) return;
    url.searchParams.delete(BOT_LINK_PARAM);
    const search = url.searchParams.toString();
    window.history.replaceState(
      window.history.state,
      "",
      `${url.pathname}${search ? `?${search}` : ""}${url.hash}`,
    );
  } catch {
    // Never break the boot over the address bar.
  }
}

function captureBotLink(): string | null {
  if (typeof window === "undefined") return null;
  const token = botLinkFromSearch(window.location.search);
  // Any `bt` (a malformed one too) leaves the URL.
  removeBotLinkFromUrl();
  if (token) {
    try {
      sessionStorage.setItem(KEYBOARD_LAUNCH_KEY, "1");
    } catch {
      // Private mode / blocked storage: the flag only helps reloads.
    }
  }
  return token;
}

let pendingToken: string | null = captureBotLink();

/** The captured token, until it has been used once. */
export function peekBotLink(): string | null {
  return pendingToken;
}

/**
 * Inside Telegram, opened from a reply-keyboard button (empty initData).
 * `telegram-web-app.js` reports `platform = "unknown"` in any normal browser;
 * Telegram passes its platform in the launch parameters (persisted by the
 * script in sessionStorage across reloads). A crafted URL can fake this, but
 * it only shows the app shell: signing in still needs a valid link plus the
 * user's explicit confirmation.
 */
export function isKeyboardLaunch(): boolean {
  const wa = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
  if (!wa || !wa.platform || wa.platform === "unknown") return false;
  if (pendingToken) return true;
  try {
    return sessionStorage.getItem(KEYBOARD_LAUNCH_KEY) === "1";
  } catch {
    return false;
  }
}

type PopupParams = {
  message: string;
  buttons: { id: string; type: "default" | "cancel"; text?: string }[];
};
type PopupCapable = { showPopup?: (params: PopupParams, cb?: (id: string) => void) => void };

/** «<name> sifatida kirasizmi?» with a «Kirish» button; resolves true only on that button. */
export async function askBotLinkLogin(name: string): Promise<boolean> {
  const lang = currentLang();
  await ensureDictionary(lang);
  const t = createT(lang);
  const message = name.trim()
    ? t("auth.botLink.confirm", { name: name.trim() })
    : t("auth.botLink.confirmNoName");
  const wa = window.Telegram?.WebApp as (TelegramWebApp & PopupCapable) | undefined;
  return new Promise<boolean>((resolve) => {
    try {
      if (wa?.showPopup && wa.isVersionAtLeast?.("6.2")) {
        wa.showPopup(
          {
            message,
            buttons: [
              { id: "login", type: "default", text: t("auth.botLink.login") },
              { id: "cancel", type: "cancel" },
            ],
          },
          (id) => resolve(id === "login"),
        );
        return;
      }
    } catch {
      // Fall through to the browser dialog.
    }
    resolve(window.confirm(message));
  });
}

/** Tell the user the link is dead and how to get a new one. */
export async function showBotLinkInvalid(): Promise<void> {
  const lang = currentLang();
  await ensureDictionary(lang);
  const message = createT(lang)("error.BOT_LINK_INVALID");
  try {
    const wa = window.Telegram?.WebApp;
    if (wa?.showAlert && wa.isVersionAtLeast?.("6.2")) {
      wa.showAlert(message);
      return;
    }
  } catch {
    // Fall through.
  }
  window.alert(message);
}

/** Mark the token used: one exchange per page load. */
export function consumeBotLink(): void {
  pendingToken = null;
}
