import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import client from "../api/client";
import {
  askBotLinkLogin,
  botLinkUserId,
  consumeBotLink,
  isKeyboardLaunch,
  peekBotLink,
  showBotLinkInvalid,
} from "../lib/botLink";
import { parseApiError } from "../lib/parseApiError";
import { useAuthStore } from "../store/auth";
import { useLangStore } from "../store/lang";
import type { UserProfile } from "../types";

type AuthResponse = {
  session_token: string;
  user: UserProfile;
};

/**
 * Returns true when the page is running inside a Telegram Mini App.
 *
 * `telegram-web-app.js` defines `window.Telegram.WebApp` in every browser, so
 * the object alone proves nothing. Telegram fills `initData` for inline/menu
 * launches; a reply-keyboard `web_app` button gives EMPTY initData, and that
 * launch is recognised by Telegram's platform launch parameter together with
 * the bot's signed `?bt=` link (`lib/botLink.ts`).
 */
export function isTelegramWebApp(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(window.Telegram?.WebApp?.initData) || isKeyboardLaunch();
}

/**
 * Bot keyboard link → session, at most once per page load (shared by React
 * StrictMode's double effect). Without the user's «Kirish» nothing is created:
 * the first call only learns whose link it is (409 `BOT_LINK_CONFIRM{name}`).
 */
let botLinkExchange: Promise<AuthResponse | null> | null = null;

function exchangeBotLinkOnce(token: string): Promise<AuthResponse | null> {
  if (!botLinkExchange) {
    consumeBotLink();
    botLinkExchange = (async () => {
      let name = "";
      try {
        await client.post("/auth/bot-link", { token, confirm: false });
        return null; // 2xx without confirm is not part of the contract
      } catch (error) {
        const { status, code, params } = parseApiError(error);
        if (status === 401 && code === "BOT_LINK_INVALID") {
          await showBotLinkInvalid();
          return null;
        }
        if (status !== 409 || code !== "BOT_LINK_CONFIRM") return null;
        name = typeof params.name === "string" ? params.name : "";
      }
      if (!(await askBotLinkLogin(name))) return null;
      try {
        const { data } = await client.post<AuthResponse>("/auth/bot-link", { token, confirm: true });
        return data;
      } catch (error) {
        if (parseApiError(error).code === "BOT_LINK_INVALID") await showBotLinkInvalid();
        return null;
      }
    })();
  }
  return botLinkExchange;
}

/**
 * Auto-authenticate Mini App users: restore the stored session, else log in
 * with Telegram initData, else (reply-keyboard launch) with the bot link.
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

    const adopt = (data: AuthResponse) => {
      useAuthStore.getState().setSession(data.session_token, data.user);
      useLangStore.getState().applyServerLang(data.user?.lang);
      // Drop any data cached under the previous account, then refetch
      // everything for the freshly authenticated user.
      queryClient.clear();
      void queryClient.invalidateQueries();
    };

    const restoreOrLogin = async () => {
      const store = useAuthStore.getState();
      const existingToken = localStorage.getItem("session_token");
      // The Telegram account currently running the Mini App: from initData,
      // else (reply keyboard) the unverified owner of the bot link.
      const botLink = peekBotLink();
      const currentTgId =
        window.Telegram?.WebApp?.initDataUnsafe?.user?.id ?? (botLink ? botLinkUserId(botLink) : null);

      if (existingToken) {
        try {
          const { data } = await client.get<UserProfile>("/auth/me");
          // Guard against a stale token left in localStorage by a *different*
          // Telegram account (same device / Telegram client shares localStorage).
          // If the restored session does not belong to the current Telegram user,
          // discard it and re-authenticate below.
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
            // The link (if any) belongs to this very session: never needed.
            if (botLink) consumeBotLink();
            return;
          }
        } catch {
          // Stale token - clear and continue to Telegram initData auth.
          if (!cancelled) {
            store.clearSession();
          }
        }
      }

      // initData stays first whenever Telegram provides it; only a launch
      // without it (reply keyboard) uses the bot link.
      const token = peekBotLink();
      if (!window.Telegram?.WebApp?.initData && (token || botLinkExchange)) {
        const data = await exchangeBotLinkOnce(token ?? "");
        if (data && !cancelled) adopt(data);
        return;
      }

      const initData = await waitForInitData();
      if (!initData) {
        return;
      }

      try {
        const { data } = await client.post<AuthResponse>("/auth/tg-webapp", {
          init_data: initData,
        });
        if (!cancelled) adopt(data);
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
