/**
 * Value helpers for `MonthYearPicker`.
 *
 * A date is stored as `"MM/YYYY"`, as a bare `"YYYY"`, or as a *present token*
 * meaning "still ongoing". The API keeps the stored string verbatim and its PDF
 * renderer recognises the token set below (`webapp/resume/i18n.py:PRESENT_TOKENS`),
 * so writing the token of the active language is what makes the generated PDF
 * read correctly.
 */
import { DEFAULT_LANG, type Lang } from "../../store/lang";

/** Lower-cased tokens the backend accepts as "until now". Keep in sync. */
export const PRESENT_TOKENS: ReadonlySet<string> = new Set([
  "hozir",
  "present",
  "now",
  "сейчас",
  "по настоящее время",
  "настоящее время",
]);

/** The token written for each language (all are members of PRESENT_TOKENS). */
export const PRESENT_VALUE: Record<Lang, string> = {
  uz: "Hozir",
  ru: "Настоящее время",
  en: "Present",
};

export function presentValueFor(lang: Lang): string {
  return PRESENT_VALUE[lang] ?? PRESENT_VALUE[DEFAULT_LANG];
}

export function isPresentValue(value: string): boolean {
  return PRESENT_TOKENS.has((value || "").trim().toLowerCase());
}

export const CURRENT_YEAR = new Date().getFullYear();

/** Years from the current one back to 1990, newest first. */
export const YEARS: string[] = Array.from({ length: CURRENT_YEAR - 1989 }, (_, i) =>
  String(CURRENT_YEAR - i),
);

function capitalize(value: string): string {
  return value ? value[0].toLocaleUpperCase() + value.slice(1) : value;
}

/** Localized month names, index 0 = January. */
export function monthNames(locale: string): string[] {
  try {
    const formatter = new Intl.DateTimeFormat(locale, { month: "long" });
    return Array.from({ length: 12 }, (_, i) => capitalize(formatter.format(new Date(2021, i, 1))));
  } catch {
    return Array.from({ length: 12 }, (_, i) => String(i + 1));
  }
}

/**
 * `"05/2023"` -> `"May 2023"`, `"2023"` -> `"2023"`, a present token -> `presentLabel`.
 * Anything else is returned unchanged.
 */
export function formatMonthYear(value: string, locale: string, presentLabel: string): string {
  const raw = (value || "").trim();
  if (!raw) return "";
  if (isPresentValue(raw)) return presentLabel;
  const [month, year] = raw.split("/");
  if (year) {
    const index = Number(month) - 1;
    if (Number.isInteger(index) && index >= 0 && index < 12) {
      return `${monthNames(locale)[index]} ${year}`;
    }
  }
  return raw;
}
