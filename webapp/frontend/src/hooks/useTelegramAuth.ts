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
 * Always re-authenticates on mount (even if a localStorage token exists) so
 * that stale / expired tokens are silently replaced before the user does
 * anything. This prevents the race condition where an old token causes an
 * immediate 401 on the first protected action.
 *
 * Some Telegram clients inject initData a few milliseconds after first render,
 * so we retry up to 4 times with increasing back-off before giving up.
 */
export default function useTelegramAuth() {
  const { setSession, setInitialized, sessionVersion } = useAuthStore();

  useEffect(() => {
    let cancelled = false;
    const MAX_ATTEMPTS = 4;
    const RETRY_DELAY_MS = 300;

    const tryAuth = async (attempt: number): Promise<void> => {
      if (cancelled) return;

      const tg = (window as Window & { Telegram?: { WebApp?: { initData?: string } } }).Telegram?.WebApp;

      if (!tg) {
        // Not inside Telegram — keep whatever state is already in localStorage.
        setInitialized();
        return;
      }

      const initData = tg.initData;

      if (!initData) {
        // SDK present but initData not injected yet — retry with back-off.
        if (attempt < MAX_ATTEMPTS) {
          await new Promise<void>((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
          return tryAuth(attempt + 1);
        }
        // Still empty after all retries — not a proper Mini App launch.
        setInitialized();
        return;
      }

      try {
        const { data } = await client.post<AuthResponse>("/auth/tg-webapp", { init_data: initData });
        if (!cancelled) setSession(data.session_token, data.user);
      } catch (err) {
        // initData invalid or network error — keep existing auth state.
        console.error("[TelegramAuth] initData auth failed:", err);
        if (!cancelled) setInitialized();
      }
    };

    void tryAuth(0);

    return () => {
      cancelled = true;
    };
  // Re-runs on mount (sessionVersion=0) and each time clearSession() is called
  // (sessionVersion increments). Does NOT re-run when setSession() succeeds,
  // preventing the double-auth that occurred when isAuthenticated changed false→true.
  }, [sessionVersion, setSession, setInitialized]);
}

