import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import client from "../api/client";
import { useAuthStore } from "../store/auth";
import { useLangStore } from "../store/lang";
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
  const queryClient = useQueryClient();
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
      // The Telegram account currently running the Mini App.
      const currentTgId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id;

      if (existingToken) {
        try {
          const { data } = await client.get<UserProfile>("/auth/me");
          // Guard against a stale token left in localStorage by a *different*
          // Telegram account (same device / Telegram client shares localStorage).
          // If the restored session does not belong to the current Telegram user,
          // discard it and re-authenticate below with the real initData.
          if (currentTgId && data.user_id !== currentTgId) {
            if (!cancelled) {
              store.clearSession();
              // Wipe cached data belonging to the previous account.
              queryClient.clear();
            }
          } else if (!cancelled) {
            store.setUser(data);
            // Boot step 2: server preference wins over the Telegram guess.
            useLangStore.getState().applyServerLang(data.lang);
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
          useLangStore.getState().applyServerLang(data.user?.lang);
          // Drop any data cached under the previous account, then refetch
          // everything for the freshly authenticated user.
          queryClient.clear();
          void queryClient.invalidateQueries();
        }
      } catch {
        // Keep app usable in readonly mode for public data.
      }
    };

    void restoreOrLogin();

    return () => {
      cancelled = true;
    };
  }, [queryClient]);
}
