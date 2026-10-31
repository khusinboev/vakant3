import { create } from "zustand";
import { persist } from "zustand/middleware";

export const LANGS = ["uz", "ru", "en"] as const;
export type Lang = (typeof LANGS)[number];
export const DEFAULT_LANG: Lang = "uz";

export const LANG_STORAGE_KEY = "vakant-lang";

/** Display metadata for the language selector. */
export const LANG_META: Record<Lang, { native: string; flag: string; locale: string }> = {
  uz: { native: "O'zbekcha", flag: "🇺🇿", locale: "uz-UZ" },
  ru: { native: "Русский", flag: "🇷🇺", locale: "ru-RU" },
  en: { native: "English", flag: "🇬🇧", locale: "en-US" },
};

/**
 * Mirrors `normalize_lang` in CONTRACT.md: lowercase, take the part before
 * `-`/`_`, map `ru*` -> ru and `en*` -> en, everything else -> uz.
 */
export function normalizeLang(code?: string | null): Lang {
  if (!code) return DEFAULT_LANG;
  const base = String(code).toLowerCase().split(/[-_]/)[0];
  if (base.startsWith("ru")) return "ru";
  if (base.startsWith("en")) return "en";
  return DEFAULT_LANG;
}

function telegramLang(): Lang {
  return normalizeLang(window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code);
}

function setHtmlLang(lang: Lang) {
  if (typeof document !== "undefined") document.documentElement.lang = lang;
}

/**
 * How a language change reaches the backend. `api/client.ts` registers the
 * real implementation at import time; keeping it injectable avoids a
 * store <-> axios-client import cycle.
 */
let langSync: ((lang: Lang) => void) | null = null;

export function setLangSync(fn: (lang: Lang) => void) {
  langSync = fn;
}

type LangState = {
  lang: Lang;
  /** True once the user picked a language by hand — the server no longer wins. */
  explicit: boolean;
  /** Pick a language: persists, tells the backend, updates <html lang>. */
  setLang: (lang: Lang) => void;
  /**
   * Boot step 2: apply `user.lang` from /auth/me or /auth/tg-webapp.
   * Ignored once the user has chosen a language explicitly.
   */
  applyServerLang: (lang?: string | null) => void;
};

export const useLangStore = create<LangState>()(
  persist(
    (set, get) => ({
      // Boot step 3: Telegram language_code (falls back to uz).
      lang: telegramLang(),
      explicit: false,
      setLang: (lang) => {
        if (get().lang === lang && get().explicit) return;
        set({ lang, explicit: true });
        setHtmlLang(lang);
        langSync?.(lang);
      },
      applyServerLang: (lang) => {
        if (get().explicit || !lang) return;
        const next = normalizeLang(lang);
        if (next !== get().lang) set({ lang: next });
        setHtmlLang(next);
      },
    }),
    {
      // Boot step 1: localStorage wins when the user chose explicitly.
      name: LANG_STORAGE_KEY,
      onRehydrateStorage: () => (state) => {
        setHtmlLang(state?.lang ?? DEFAULT_LANG);
      },
    },
  ),
);

/** Non-reactive read, for axios interceptors and other non-React code. */
export function currentLang(): Lang {
  return useLangStore.getState().lang;
}
