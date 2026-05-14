import { create } from "zustand";

import type { UserProfile } from "../types";

type AuthState = {
  user: UserProfile | null;
  isAuthenticated: boolean;
  /** true while the initial Telegram initData auth is still in flight */
  isInitializing: boolean;
  setSession: (token: string, user: UserProfile) => void;
  clearSession: () => void;
  setUser: (user: UserProfile | null) => void;
  setInitialized: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: Boolean(localStorage.getItem("session_token")),
  // Always show a spinner on first load — useTelegramAuth will always attempt
  // a fresh token exchange so we get a valid token before the user acts.
  isInitializing: true,
  setSession: (token, user) => {
    localStorage.setItem("session_token", token);
    set({ user, isAuthenticated: true, isInitializing: false });
  },
  clearSession: () => {
    localStorage.removeItem("session_token");
    // isInitializing = true so pages show a spinner while re-auth runs
    set({ user: null, isAuthenticated: false, isInitializing: true });
  },
  setUser: (user) => set({ user, isAuthenticated: Boolean(user || localStorage.getItem("session_token")) }),
  setInitialized: () => set({ isInitializing: false }),
}));
