import { useEffect } from "react";

import {
  useThemeStore,
  type ResolvedTheme,
  type ThemeMode,
} from "../store/theme";

function applyToDocument(resolved: ResolvedTheme) {
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.dataset.theme = resolved;
  root.style.colorScheme = resolved;
}

/**
 * Applies the resolved theme to <html> and keeps it in sync with the OS
 * (`prefers-color-scheme`) and with Telegram (`themeChanged` → `colorScheme`).
 *
 * Call once, next to `useTelegramWebApp()` in App.
 * Returns the current mode / resolved theme and a setter, so a settings UI can
 * use this hook alone.
 */
export default function useTheme(): {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
} {
  const mode = useThemeStore((s) => s.mode);
  const resolved = useThemeStore((s) => s.resolved);
  const setMode = useThemeStore((s) => s.setMode);
  const syncResolved = useThemeStore((s) => s.syncResolved);

  // Paint synchronously on the very first render so there is no flash.
  useEffect(() => {
    applyToDocument(resolved);
  }, [resolved]);

  useEffect(() => {
    // Make sure the mode restored from localStorage is re-resolved once the
    // Telegram SDK / matchMedia are available.
    syncResolved();

    const mql = window.matchMedia?.("(prefers-color-scheme: dark)");
    const onSystemChange = () => syncResolved();
    mql?.addEventListener?.("change", onSystemChange);

    const webApp = window.Telegram?.WebApp;
    const onTelegramChange = () => syncResolved();
    webApp?.onEvent?.("themeChanged", onTelegramChange);

    return () => {
      mql?.removeEventListener?.("change", onSystemChange);
      webApp?.offEvent?.("themeChanged", onTelegramChange);
    };
  }, [syncResolved]);

  return { mode, resolved, setMode };
}

export { applyToDocument as applyThemeToDocument };
