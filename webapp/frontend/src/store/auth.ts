import { create } from "zustand";

import type { StoredSession } from "../lib/authPlan";
import type { UserProfile } from "../types";

const TOKEN_KEY = "session_token";
/** Whose session `session_token` is: compared with the current Telegram account on launch. */
const USER_ID_KEY = "session_user_id";

function storageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** The stored Bearer session and its owner (`userId` null for sessions stored by older builds). */
export function readStoredSession(): StoredSession | null {
  const token = storageGet(TOKEN_KEY);
  if (!token) return null;
  const raw = Number(storageGet(USER_ID_KEY));
  return { token, userId: Number.isSafeInteger(raw) && raw > 0 ? raw : null };
}

function writeSession(token: string, userId: number | null): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    if (userId) localStorage.setItem(USER_ID_KEY, String(userId));
    else localStorage.removeItem(USER_ID_KEY);
  } catch {
    // Blocked storage (private mode): nothing to persist.
  }
}

function removeSession(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_ID_KEY);
  } catch {
    // Nothing stored.
  }
}

type AuthState = {
  user: UserProfile | null;
  isAuthenticated: boolean;
  setSession: (token: string, user: UserProfile) => void;
  /** Put back a session kept aside (bot-link fallback); `/auth/me` then loads the user. */
  restoreSession: (session: StoredSession) => void;
  clearSession: () => void;
  setUser: (user: UserProfile | null) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: Boolean(storageGet(TOKEN_KEY)),
  setSession: (token, user) => {
    writeSession(token, user?.user_id ?? null);
    set({ user, isAuthenticated: true });
  },
  restoreSession: (session) => {
    writeSession(session.token, session.userId);
    set({ user: null, isAuthenticated: true });
  },
  clearSession: () => {
    removeSession();
    set({ user: null, isAuthenticated: false });
  },
  setUser: (user) => {
    const stored = readStoredSession();
    // Record the owner of a session stored by an older build (no user id yet).
    if (user && stored && stored.userId === null) writeSession(stored.token, user.user_id);
    set({ user, isAuthenticated: Boolean(user || stored) });
  },
}));
