import { useEffect } from "react";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";

type AuthResponse = { session_token: string; user: UserProfile };

/**
 * Returns true when the page is running inside Telegram WebApp.
 * Checks for the WebApp object — NOT initData — because initData can be an
 * empty string on the very first render frame even inside Telegram.
 */
export function isTelegramWebApp(): boolean {
  return Boolean(
    typeof window !== "undefined" &&
      (window as Window & { Telegram?: { WebApp?: unknown } }).Telegram?.WebApp
  );
}

/**
 * Authenticates the user via Telegram.WebApp.initData.
 *
 * Some Telegram clients (especially desktop) inject initData a few
 * milliseconds after the page first renders, so we retry up to 4 times
 * with increasing delays before giving up and marking initialization done.
 */
export default function useTelegramAuth() {
  const { setSession, setInitialized, isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      setInitialized();
      return;
    }

    let cancelled = false;
    const MAX_ATTEMPTS = 4;
    const RETRY_DELAY_MS = 300;

    const tryAuth = async (attempt: number): Promise<void> => {
      if (cancelled) return;

      const tg = (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp;

      if (!tg) {
        // Not inside any Telegram client
        setInitialized();
        return;
      }

      const initData = tg.initData;

      if (!initData) {
        // SDK present but initData not injected yet — retry with back-off
        if (attempt < MAX_ATTEMPTS) {
          await new Promise<void>((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
          return tryAuth(attempt + 1);
        }
        // Still empty after all retries — not a proper Mini App launch
        setInitialized();
        return;
      }

      try {
        const { data } = await client.post<AuthResponse>("/auth/tg-webapp", { init_data: initData });
        if (!cancelled) setSession(data.session_token, data.user);
      } catch (err) {
        // initData invalid, expired, or network error — continue as guest
        console.error("[TelegramAuth] initData auth failed:", err);
        if (!cancelled) setInitialized();
      }
    };

    void tryAuth(0);

    return () => {
      cancelled = true;
    };
  // Re-runs when session is cleared (stale 401) so initData auth is retried.
  }, [isAuthenticated, setSession, setInitialized]);
}

