import axios from "axios";

import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";
import { currentLang, setLangSync } from "../store/lang";
import { parseApiError } from "../lib/parseApiError";

declare module "axios" {
  interface AxiosRequestConfig {
    /** Set on the one replay after a 401 re-login, so it can never loop. */
    _authRetried?: boolean;
  }
}

const client = axios.create({
  baseURL: "/api"
});

const LOGIN_PATH = "/auth/tg-webapp";

/** After a transient login failure (429, 5xx, network), wait this long before trying again. */
const RELOGIN_COOLDOWN_MS = 30_000;

/**
 * One in-flight re-login shared by every request that hit the 401.
 * - The login answering 401 means the initData itself is rejected (e.g. older
 *   than the API's 300 s window). It never changes within a page session, so
 *   re-login stays off for good.
 * - Any other failure (rate limit, 5xx, network) is transient: re-login is
 *   allowed again after a short cooldown, so it can never loop.
 */
let relogin: Promise<boolean> | null = null;
let reloginRejected = false;
let reloginBlockedUntil = 0;

function bearer(): string {
  const token = localStorage.getItem("session_token");
  return token ? `Bearer ${token}` : "";
}

function reloginWithInitData(): Promise<boolean> {
  const initData = window.Telegram?.WebApp?.initData;
  if (!initData || reloginRejected) return Promise.resolve(false);
  if (!relogin && Date.now() < reloginBlockedUntil) return Promise.resolve(false);
  if (!relogin) {
    relogin = client
      .post<{ session_token: string; user: UserProfile }>(
        LOGIN_PATH,
        { init_data: initData },
        { _authRetried: true },
      )
      .then(({ data }) => {
        useAuthStore.getState().setSession(data.session_token, data.user);
        return true;
      })
      .catch((loginError: unknown) => {
        if (parseApiError(loginError).status === 401) reloginRejected = true;
        else reloginBlockedUntil = Date.now() + RELOGIN_COOLDOWN_MS;
        return false;
      })
      .finally(() => {
        relogin = null;
      });
  }
  return relogin;
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("session_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Saves endpoints can identify user by Telegram initData even without webapp session auth.
  const initData = window.Telegram?.WebApp?.initData;
  if (initData) {
    config.headers["X-Telegram-Init-Data"] = initData;
  }

  const tgUserId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;
  if (tgUserId) {
    config.headers["X-Telegram-User-Id"] = String(tgUserId);
  }

  // The API resolves the response language from this header (see CONTRACT.md).
  config.headers["Accept-Language"] = currentLang();

  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { status, code } = parseApiError(error);
    // A dead session must not linger in localStorage: the next request would
    // keep sending it and every retry would fail the same way.
    // A refused bot link (BOT_LINK_INVALID) says nothing about the session we hold.
    if (status === 401 && code !== "INVALID_INIT_DATA" && code !== "BOT_LINK_INVALID") {
      const config = axios.isAxiosError(error) ? error.config : undefined;
      const replayable = Boolean(config && !config._authRetried && config.url !== LOGIN_PATH);
      const sentAuth = String(config?.headers?.Authorization ?? "");
      const currentAuth = bearer();

      if (sentAuth === currentAuth) {
        // The token that failed is the one we hold: a dead session must not
        // linger in localStorage, or every later request fails the same way.
        if (useAuthStore.getState().isAuthenticated) useAuthStore.getState().clearSession();
      } else if (replayable && config && currentAuth) {
        // Sent with an older token that a finished re-login already replaced:
        // keep the new session and just replay with it.
        return client.request({ ...config, _authRetried: true });
      }

      // Inside Telegram the initData can mint a fresh session: do that once
      // and replay the request once, instead of staying logged out.
      if (replayable && config && (await reloginWithInitData())) {
        return client.request({ ...config, _authRetried: true });
      }
    }
    return Promise.reject(error);
  }
);

// Persist the user's language choice server-side (PATCH /api/profile/lang).
// A failure is non-fatal: the preference is local-first.
setLangSync((lang) => {
  void client.patch("/profile/lang", { lang }).catch(() => undefined);
});

export default client;
