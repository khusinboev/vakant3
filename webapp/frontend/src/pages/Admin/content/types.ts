import type { LocalizedText } from "../../../api/adminTypes";
import type { Lang } from "../../../store/lang";
import { isHtmlAllowed } from "./richtext";

export type { LocalizedText, Lang };

export function emptyLocalized(): LocalizedText {
  return { uz: "", ru: "", en: "" };
}

/** Reads one language out of a `LocalizedText`, `undefined` -> `""`. */
export function localizedValue(text: LocalizedText | undefined, lang: Lang): string {
  return (text?.[lang] ?? "") as string;
}

export function setLocalizedValue(text: LocalizedText, lang: Lang, value: string): LocalizedText {
  return { ...text, [lang]: value };
}

export type FieldErrorKind = "required" | "tooLong" | "invalidHtml";

/** Client-side mirror of the backend's per-field/per-language checks (soft hints only). */
export function validateLocalizedField(
  text: LocalizedText,
  opts: { requireUz: boolean; maxLen: number },
): Partial<Record<Lang, FieldErrorKind>> {
  const errors: Partial<Record<Lang, FieldErrorKind>> = {};
  (["uz", "ru", "en"] as Lang[]).forEach((lang) => {
    const raw = localizedValue(text, lang);
    if (lang === "uz" && opts.requireUz && !raw.trim()) {
      errors[lang] = "required";
      return;
    }
    if (raw.length > opts.maxLen) {
      errors[lang] = "tooLong";
      return;
    }
    if (raw && !isHtmlAllowed(raw)) {
      errors[lang] = "invalidHtml";
    }
  });
  return errors;
}

export function hasAnyError(errors: Partial<Record<Lang, FieldErrorKind>>): boolean {
  return Object.values(errors).some(Boolean);
}
