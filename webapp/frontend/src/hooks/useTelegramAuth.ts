import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import client from "../api/client";
import { isAccountSwitch, planAuthBoot, userScopedKeys, type AuthBootPlan } from "../lib/authPlan";
import {
  botLinkUserId,
  consumeBotLink,
  isKeyboardLaunch,
  peekBotLink,
  showBotLinkInvalid,
} from "../lib/botLink";
import { parseApiError } from "../lib/parseApiError";
import { readStoredSession, useAuthStore } from "../store/auth";
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

type Boot = { plan: AuthBootPlan; previousUserId: number | null };

/**
 * The launch's identity decision (`lib/authPlan.ts`), made once and
 * synchronously when this module loads: before React renders and before any
 * query runs. A stored session that is not the current Telegram account's is
 * dropped right here, so no request ever leaves with another account's token.
 */
function decideBoot(): Boot | null {
  if (!isTelegramWebApp()) return null;
  const wa = window.Telegram?.WebApp;
  const stored = readStoredSession();
  const botLink = peekBotLink();
  const plan = planAuthBoot({
    hasInitData: Boolean(wa?.initData),
    initDataUserId: wa?.initDataUnsafe?.user?.id ?? null,
    botLink,
    botLinkUserId: botLink ? botLinkUserId(botLink) : null,
    stored,
  });
  if ((plan.kind === "initData" || plan.kind === "botLink") && plan.clearStored) {
    useAuthStore.getState().clearSession();
  }
  // initData wins over a link: the link is never used then.
  if (plan.kind !== "botLink" && botLink) consumeBotLink();
  return { plan, previousUserId: stored?.userId ?? null };
}

const boot: Boot | null = decideBoot();
/** The account whose data this page may currently hold. */
let knownUserId: number | null = boot?.previousUserId ?? null;
/** One bootstrap per page load (React StrictMode runs effects twice). */
let bootRun: Promise<void> | null = null;

/** Remove what the previous account left on this device. */
function forgetAccount(userId: number): void {
  try {
    for (const key of userScopedKeys(Object.keys(localStorage), userId)) localStorage.removeItem(key);
  } catch {
    // Blocked storage: nothing was stored either.
  }
  // That account's explicit language choice is not the new account's.
  useLangStore.setState({ explicit: false });
}

function adopt(queryClient: QueryClient, data: AuthResponse): void {
  const nextUserId = data.user.user_id;
  if (knownUserId !== null && isAccountSwitch(knownUserId, nextUserId)) forgetAccount(knownUserId);
  knownUserId = nextUserId;
  useAuthStore.getState().setSession(data.session_token, data.user);
  useLangStore.getState().applyServerLang(data.user?.lang);
  // Drop every cached answer (gate/admin role included) and refetch the
  // active queries as the freshly authenticated user.
  void queryClient.resetQueries();
}

async function loginWithInitData(queryClient: QueryClient, initData: string): Promise<void> {
  try {
    const { data } = await client.post<AuthResponse>("/auth/tg-webapp", { init_data: initData });
    adopt(queryClient, data);
  } catch {
    // Keep app usable in readonly mode for public data.
  }
}

async function waitForInitData(): Promise<string> {
  for (let i = 0; i < 10; i += 1) {
    const initData = window.Telegram?.WebApp?.initData;
    if (initData) return initData;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return "";
}

/**
 * Load the user of the stored session. A different current Telegram account
 * (initData arrived late) replaces it. Returns false when there is no usable
 * session afterwards.
 */
async function loadStoredUser(queryClient: QueryClient): Promise<boolean> {
  try {
    const { data } = await client.get<UserProfile>("/auth/me");
    const wa = window.Telegram?.WebApp;
    const currentTgId = wa?.initDataUnsafe?.user?.id;
    if (wa?.initData && currentTgId && data.user_id !== currentTgId) {
      useAuthStore.getState().clearSession();
      knownUserId = data.user_id;
      await loginWithInitData(queryClient, wa.initData);
      return true;
    }
    knownUserId = data.user_id;
    useAuthStore.getState().setUser(data);
    // Boot step 2: server preference wins over the Telegram guess.
    useLangStore.getState().applyServerLang(data.lang);
    return true;
  } catch {
    // A 401 already cleared the session in the client interceptor (and, with
    // initData, re-logged in and replayed this call).
    return useAuthStore.getState().isAuthenticated;
  }
}

async function exchangeBotLink(
  queryClient: QueryClient,
  plan: Extract<AuthBootPlan, { kind: "botLink" }>,
): Promise<void> {
  const token = peekBotLink();
  consumeBotLink();
  if (!token) return;
  try {
    const { data } = await client.post<AuthResponse>("/auth/bot-link", { token });
    adopt(queryClient, data);
    return;
  } catch (error) {
    if (plan.fallback) {
      // The link's owner already had a session here: keep using it.
      useAuthStore.getState().restoreSession(plan.fallback);
      if (await loadStoredUser(queryClient)) return;
    }
    if (parseApiError(error).code === "BOT_LINK_INVALID") await showBotLinkInvalid();
  }
}

async function runBoot(queryClient: QueryClient, plan: AuthBootPlan): Promise<void> {
  switch (plan.kind) {
    case "reuse":
    case "restore":
      if (await loadStoredUser(queryClient)) return;
      break;
    case "initData":
      await loginWithInitData(queryClient, window.Telegram?.WebApp?.initData ?? "");
      return;
    case "botLink":
      await exchangeBotLink(queryClient, plan);
      return;
    case "none":
      break;
  }
  const initData = await waitForInitData();
  if (initData) await loginWithInitData(queryClient, initData);
}

/**
 * Auto-authenticate Mini App users as the CURRENT Telegram account, never
 * with a prompt: initData first, else the bot keyboard link, else the stored
 * session (`lib/authPlan.ts`).
 */
export default function useTelegramAuth() {
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!boot) return;
    bootRun ??= runBoot(queryClient, boot.plan);
  }, [queryClient]);
}
