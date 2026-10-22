import type { TFunction, TranslationKey } from "../../i18n";
import { apiErrorMessage, parseApiError } from "../../lib/parseApiError";

/** Click's decline reason (`CLICK_DECLINED{reason}`) gets its own text; the rest go through `error.<CODE>`. */
export function paymentErrorMessage(error: unknown, t: TFunction): string {
  const parsed = parseApiError(error);
  if (parsed.code === "CLICK_DECLINED" && typeof parsed.params.reason === "string") {
    const key = `payments.reason.${parsed.params.reason}` as TranslationKey;
    const text = t(key);
    if (text !== key) return text;
  }
  return apiErrorMessage(error, t);
}

export const inputCls =
  "w-full rounded-xl border border-border bg-surface px-3.5 py-3 text-base text-text outline-none placeholder:text-muted focus:border-primary disabled:opacity-60";
export const fieldLabel = "mb-1.5 block text-sm font-medium text-muted";
export const fieldError = "mt-1.5 text-[13px] text-danger";
export const primaryBtn =
  "tap-target w-full rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primaryFg disabled:opacity-60";
export const textBtn = "tap-target rounded-lg px-2 py-1 text-sm font-medium text-primary disabled:opacity-50";
