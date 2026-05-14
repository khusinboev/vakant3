import { useEffect } from "react";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";

type AuthResponse = { session_token: string; user: UserProfile };

/**
 * Returns true when the page is running inside Telegram WebApp.
 * We check for the WebApp object itself — NOT initData — because initData can
 * be an empty string on some platforms/versions at the moment React first renders,
 * even though the app is legitimately inside Telegram.
 */
export function isTelegramWebApp(): boolean {
  return Boolean(
    typeof window !== "undefined" &&
      (window as Window & { Telegram?: { WebApp?: unknown } }).Telegram?.WebApp
  );
}

/**
 * On mount, if the app is opened inside Telegram and the user is not yet
 * authenticated, automatically calls POST /auth/tg-webapp with the raw
 * initData string.  Telegram signs this with the bot token so the backend
 * can verify it via HMAC-SHA256.
 * Marks isInitializing=false after the attempt finishes (success or failure)
 * so the UI knows the auth window is over.
 */
export default function useTelegramAuth() {
  const { setSession, setInitialized, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      setInitialized();
      return;
    }

    const tg = (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp;
    const initData = tg?.initData;

    if (!initData) {
      // Not inside Telegram, or SDK not available — no auto-auth possible
      setInitialized();
      return;
    }

    void (async () => {
      try {
        const { data } = await client.post<AuthResponse>("/auth/tg-webapp", { init_data: initData });
        setSession(data.session_token, data.user); // also sets isInitializing=false
      } catch {
        // initData invalid or expired — user continues as guest
        setInitialized();
      }
    })();
  // isAuthenticated dependency: re-runs when session is cleared (stale token 401)
  // so initData auth is retried automatically without a page reload.
  }, [isAuthenticated, setSession, setInitialized]);
}
