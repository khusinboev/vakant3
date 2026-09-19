/**
 * Frontend i18n. Uzbek is the source language; ru/en are typed against it.
 *
 * ── Adding a namespace (e.g. `resume`, `admin`) ────────────────────────────
 *  1. create `src/i18n/uz/<ns>.ts`   -> `const x = {...}; export type XDict = typeof x; export default x;`
 *  2. create `src/i18n/ru/<ns>.ts` and `src/i18n/en/<ns>.ts`
 *     -> `const x: Record<keyof XDict, string> = {...}; export default x;`
 *     (a missing or misspelled key is then a compile error)
 *  3. add ONE import line to each of the three blocks below and list it in the
 *     matching merge.
 *
 * Key convention: flat, dot separated, `<area>.<name>` — e.g. `profile.title`,
 * `vacancy.row.gender`, `error.PRO_REQUIRED`. Placeholders are `{name}`.
 */
import { DEFAULT_LANG, LANGS, type Lang } from "../store/lang";

import uzCommon from "./uz/common";
import uzVacancy from "./uz/vacancy";
import uzResume from "./uz/resume";
import uzAdmin from "./uz/admin";

// uz is bundled eagerly (it is the type source and the fallback); ru/en are
// loaded on demand as separate chunks via `ensureDictionary`.
const uz = { ...uzCommon, ...uzVacancy, ...uzResume, ...uzAdmin };

/** Every valid translation key. Passing anything else to `t()` is a type error. */
export type TranslationKey = keyof typeof uz;

export type TranslationVars = Record<string, string | number>;

type Dictionary = Partial<Record<TranslationKey, string>>;

export const dictionaries: Record<Lang, Dictionary> = { uz, ru: {}, en: {} };

type LazyLang = Exclude<Lang, "uz">;

const loaders: Record<LazyLang, () => Promise<{ default: Dictionary }>> = {
  ru: () => import("./ru"),
  en: () => import("./en"),
};

const pending: Partial<Record<Lang, Promise<void>>> = {};
let version = 0;
const listeners = new Set<() => void>();

/** Bumps when a dictionary finishes loading; `useT` re-renders on it. */
export function getDictionaryVersion(): number {
  return version;
}

export function subscribeDictionaries(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Resolve once `lang`'s dictionary is in memory (no-op for uz / already loaded). */
export function ensureDictionary(lang: Lang): Promise<void> {
  if (lang === DEFAULT_LANG || Object.keys(dictionaries[lang]).length > 0) return Promise.resolve();
  const inFlight = pending[lang];
  if (inFlight) return inFlight;
  const job = loaders[lang as LazyLang]()
    .then((mod) => {
      dictionaries[lang] = mod.default;
      version += 1;
      listeners.forEach((fn) => fn());
    })
    .catch(() => {
      // Keep the uz fallback; a later call may retry.
    })
    .finally(() => {
      delete pending[lang];
    });
  pending[lang] = job;
  return job;
}

const PLACEHOLDER = /\{(\w+)\}/g;

function interpolate(template: string, vars?: TranslationVars): string {
  if (!vars) return template;
  return template.replace(PLACEHOLDER, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

export type TFunction = (key: TranslationKey, vars?: TranslationVars) => string;

/** Build a translator for a language. Falls back to uz, then to the key itself. */
export function createT(lang: Lang): TFunction {
  const primary = dictionaries[lang] ?? dictionaries[DEFAULT_LANG];
  const fallback = dictionaries[DEFAULT_LANG];
  return (key, vars) => interpolate(primary[key] ?? fallback[key] ?? key, vars);
}

/** Resolve an integer vacancy code through a namespaced map, e.g. `vacancy.gender`. */
export type VacancyCodeGroup =
  | "vacancy.gender"
  | "vacancy.work_type"
  | "vacancy.busyness"
  | "vacancy.payment"
  | "vacancy.education"
  | "vacancy.experience";

export { DEFAULT_LANG, LANGS };
export type { Lang };
