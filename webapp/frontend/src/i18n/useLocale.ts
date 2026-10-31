import { useMemo } from "react";

import { LANG_META, useLangStore, type Lang } from "../store/lang";

export type Locale = {
  lang: Lang;
  /** BCP-47 tag for Intl, e.g. "ru-RU". */
  locale: string;
  /** 1234567 -> "1 234 567" (grouped for the active locale). */
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) => string;
  /** Number + the localized currency word, e.g. "1 234 567 so'm". */
  formatMoney: (value: number) => string;
  /** Date | number (unix seconds or ms) | ISO string -> "12.03.2025". */
  formatDate: (value: Date | number | string, options?: Intl.DateTimeFormatOptions) => string;
  formatDateTime: (value: Date | number | string) => string;
};

const CURRENCY_WORD: Record<Lang, string> = { uz: "so'm", ru: "сум", en: "UZS" };

function toDate(value: Date | number | string): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  if (typeof value === "number") {
    // Unix seconds (the API sends seconds) vs milliseconds.
    const ms = value < 1e12 ? value * 1000 : value;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Intl number/date formatting bound to the language store.
 * Use this instead of ad-hoc `toLocaleString("uz-UZ")` calls.
 */
export function useLocale(): Locale {
  const lang = useLangStore((s) => s.lang);

  return useMemo(() => {
    const locale = LANG_META[lang].locale;
    const formatNumber = (value: number, options?: Intl.NumberFormatOptions) => {
      if (!Number.isFinite(value)) return "";
      try {
        return new Intl.NumberFormat(locale, options).format(value);
      } catch {
        return String(value);
      }
    };
    const formatDate = (value: Date | number | string, options?: Intl.DateTimeFormatOptions) => {
      const date = toDate(value);
      if (!date) return "";
      try {
        return new Intl.DateTimeFormat(
          locale,
          options ?? { day: "2-digit", month: "2-digit", year: "numeric" },
        ).format(date);
      } catch {
        return date.toISOString().slice(0, 10);
      }
    };

    return {
      lang,
      locale,
      formatNumber,
      formatMoney: (value) => `${formatNumber(value)} ${CURRENCY_WORD[lang]}`,
      formatDate,
      formatDateTime: (value) =>
        formatDate(value, {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
    };
  }, [lang]);
}

export default useLocale;
