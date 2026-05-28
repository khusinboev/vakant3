import { useEffect } from "react";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import type { UserProfile } from "../types";

type AuthResponse = {
  session_token: string;
  user: UserProfile;
};

/**
 * Returns true when the page is running inside Telegram WebApp.
 */
export function isTelegramWebApp(): boolean {
  return Boolean(
    typeof window !== "undefined" &&
      (window as Window & { Telegram?: { WebApp?: unknown } }).Telegram?.WebApp
  );
}

/**
 * Auto-authenticate Mini App users via Telegram initData.
 * This ensures users who open from bot WebApp buttons get a valid session_token.
 */
export default function useTelegramAuth() {
  useEffect(() => {
    if (!isTelegramWebApp()) {
      return;
    }

    let cancelled = false;

    const waitForInitData = async (): Promise<string> => {
      for (let i = 0; i < 10; i += 1) {
        const initData = window.Telegram?.WebApp?.initData;
        if (initData) {
          return initData;
        }
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
      return "";
    };

    const restoreOrLogin = async () => {
      const store = useAuthStore.getState();
      const existingToken = localStorage.getItem("session_token");

      if (existingToken) {
        try {
          const { data } = await client.get<UserProfile>("/auth/me");
          if (!cancelled) {
            store.setUser(data);
            return;
          }
        } catch {
          // Stale token - clear and continue to Telegram initData auth.
          if (!cancelled) {
            store.clearSession();
          }
        }
      }

      const initData = await waitForInitData();
      if (!initData) {
        return;
      }

      try {
        const { data } = await client.post<AuthResponse>("/auth/tg-webapp", {
          init_data: initData,
        });

        if (!cancelled) {
          store.setSession(data.session_token, data.user);
        }
      } catch {
        // Keep app usable in readonly mode for public data.
      }
    };

    void restoreOrLogin();

    return () => {
      cancelled = true;
    };
  }, []);
}
