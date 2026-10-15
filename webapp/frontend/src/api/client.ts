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

/**
 * One in-flight re-login shared by every request that hit the 401. A failed
 * attempt is remembered: the Mini App's initData never changes within a page
 * session, so once it is rejected (e.g. older than the API's 300 s window)
 * trying again would only fail the same way.
 */
let relogin: Promise<boolean> | null = null;
let reloginRejected = false;

function reloginWithInitData(): Promise<boolean> {
  const initData = window.Telegram?.WebApp?.initData;
  if (!initData || reloginRejected) return Promise.resolve(false);
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
      .catch(() => {
        reloginRejected = true;
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
    if (status === 401 && code !== "INVALID_INIT_DATA") {
      if (useAuthStore.getState().isAuthenticated) useAuthStore.getState().clearSession();
      // Inside Telegram the initData can mint a fresh session: do that once
      // and replay the request once, instead of staying logged out.
      const config = axios.isAxiosError(error) ? error.config : undefined;
      if (config && !config._authRetried && config.url !== LOGIN_PATH && (await reloginWithInitData())) {
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
