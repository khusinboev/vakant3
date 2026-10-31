import { useEffect, useMemo, useSyncExternalStore } from "react";

import { useLangStore, type Lang } from "../store/lang";
import {
  createT,
  ensureDictionary,
  getDictionaryVersion,
  subscribeDictionaries,
  type TFunction,
  type TranslationKey,
  type VacancyCodeGroup,
} from "./index";

/**
 * The translator, bound to the current language store.
 *
 *   const t = useT();
 *   t("profile.title")                       // "Profil"
 *   t("home.count", { n: 42 })               // "42 ta vakansiya"
 *
 * Unknown keys are a compile error. A key missing from ru/en falls back to uz.
 */
export function useT(): TFunction {
  const lang = useLangStore((s) => s.lang);
  const version = useSyncExternalStore(subscribeDictionaries, getDictionaryVersion);
  useEffect(() => {
    void ensureDictionary(lang);
  }, [lang]);
  // `version` is a dependency on purpose: it changes when a lazy dictionary lands.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => createT(lang), [lang, version]);
}

/** The active language code, for components that need it directly. */
export function useLang(): Lang {
  return useLangStore((s) => s.lang);
}

/**
 * Turns the raw integer codes from `GET /jobs/{uid}` (`data.normalized.codes`)
 * into localized labels.
 *
 *   const label = useVacancyCodeLabel();
 *   label("vacancy.gender", codes.gender)    // "Ayol" | null
 *
 * Returns null for null/undefined/non-numeric input, and a "Kod {n}" style
 * placeholder for a code the maps do not know.
 */
export function useVacancyCodeLabel(): (group: VacancyCodeGroup, code: unknown) => string | null {
  const t = useT();
  return useMemo(
    () => (group, code) => {
      const n = typeof code === "number" ? code : Number(code);
      if (code === null || code === undefined || code === "" || !Number.isFinite(n)) return null;
      const key = `${group}.${n}` as TranslationKey;
      const label = t(key);
      return label === key ? t("vacancy.unknownCode", { code: n }) : label;
    },
    [t],
  );
}

export default useT;
