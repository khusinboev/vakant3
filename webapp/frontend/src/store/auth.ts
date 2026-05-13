import { create } from "zustand";

import type { UserProfile } from "../types";

type AuthState = {
  user: UserProfile | null;
  isAuthenticated: boolean;
  setSession: (token: string, user: UserProfile) => void;
  clearSession: () => void;
  setUser: (user: UserProfile | null) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: Boolean(localStorage.getItem("session_token")),
  setSession: (token, user) => {
    localStorage.setItem("session_token", token);
    set({ user, isAuthenticated: true });
  },
  clearSession: () => {
    localStorage.removeItem("session_token");
    set({ user: null, isAuthenticated: false });
  },
  setUser: (user) => set({ user, isAuthenticated: Boolean(user || localStorage.getItem("session_token")) })
}));
