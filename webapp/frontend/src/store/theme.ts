import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Theme preference.
 *  - "telegram" → follow Telegram's own colorScheme (default inside the Mini App)
 *  - "system"   → follow the OS via prefers-color-scheme (default outside Telegram)
 *  - "light" / "dark" → forced
 */
export type ThemeMode = "system" | "telegram" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export const THEME_MODES: ThemeMode[] = ["telegram", "light", "dark", "system"];

export const THEME_STORAGE_KEY = "vakant-theme";

function insideTelegram(): boolean {
  return typeof window !== "undefined" && Boolean(window.Telegram?.WebApp);
}

export function defaultThemeMode(): ThemeMode {
  return insideTelegram() ? "telegram" : "system";
}

function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

function telegramPrefersDark(): boolean {
  const scheme = window.Telegram?.WebApp?.colorScheme;
  if (scheme === "dark") return true;
  if (scheme === "light") return false;
  // Telegram did not report a scheme (old client / outside TG) — fall back to OS.
  return systemPrefersDark();
}

/** Resolve a mode to the concrete theme that should be painted right now. */
export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  if (mode === "light") return "light";
  if (mode === "dark") return "dark";
  if (mode === "telegram") return telegramPrefersDark() ? "dark" : "light";
  return systemPrefersDark() ? "dark" : "light";
}

type ThemeState = {
  mode: ThemeMode;
  /** The theme currently applied to <html>. */
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
  /** Internal: re-resolve after a matchMedia / Telegram themeChanged event. */
  syncResolved: () => void;
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: defaultThemeMode(),
      resolved: resolveTheme(defaultThemeMode()),
      setMode: (mode) => set({ mode, resolved: resolveTheme(mode) }),
      syncResolved: () => {
        const next = resolveTheme(get().mode);
        if (next !== get().resolved) set({ resolved: next });
      },
    }),
    {
      name: THEME_STORAGE_KEY,
      // `resolved` is always derived — never restore a stale value.
      partialize: (state) => ({ mode: state.mode }),
      onRehydrateStorage: () => (state) => {
        if (state) state.resolved = resolveTheme(state.mode);
      },
    },
  ),
);
