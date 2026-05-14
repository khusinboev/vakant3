import { useEffect } from "react";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";

type AuthResponse = { session_token: string; user: UserProfile };

/** Returns true when the page is running inside Telegram WebApp (initData present). */
export function isTelegramWebApp(): boolean {
  return Boolean(
    typeof window !== "undefined" &&
      (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp?.initData
  );
}

/**
 * On mount, if the app is opened inside Telegram and the user is not yet
 * authenticated, automatically calls POST /auth/tg-webapp with the raw
 * initData string.  Telegram signs this with the bot token so the backend
 * can verify it via HMAC-SHA256.
 */
export default function useTelegramAuth() {
  const { setSession, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) return;

    const tg = (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp;
    const initData = tg?.initData;
    if (!initData) return;

    void (async () => {
      try {
        const { data } = await client.post<AuthResponse>("/auth/tg-webapp", { init_data: initData });
        setSession(data.session_token, data.user);
      } catch {
        // initData invalid or expired — user continues as guest
      }
    })();
  // isAuthenticated dependency: re-runs when session is cleared (e.g. stale token)
  // so initData auth is retried automatically without a page reload.
  }, [isAuthenticated, setSession]);
}
