import axios from "axios";

import { useAuthStore } from "../store/auth";
import { currentLang, setLangSync } from "../store/lang";
import { parseApiError } from "../lib/parseApiError";

const client = axios.create({
  baseURL: "/api"
});

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
  (error) => {
    const { status, code } = parseApiError(error);
    // A dead session must not linger in localStorage: the next request would
    // keep sending it and every retry would fail the same way.
    if (status === 401 && code !== "INVALID_INIT_DATA") {
      if (useAuthStore.getState().isAuthenticated) useAuthStore.getState().clearSession();
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
