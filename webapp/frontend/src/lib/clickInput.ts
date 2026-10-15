/**
 * Input rules for the Click top-up forms (port of SlaydX `lib/click-input.ts` and
 * `lib/topup-limits.ts`). The server validates with the same rules
 * (`webapp/payments/config.py`); these only drive inline hints. Errors are
 * translation keys, never prose.
 */
import type { TranslationKey } from "../i18n";

export const MIN_TOPUP = 1_000;
export const MAX_TOPUP = 10_000_000;
export const TOPUP_PRESETS = [10_000, 25_000, 50_000, 100_000] as const;
export const DEFAULT_TOPUP = 25_000;
/** Seconds before "resend code" unlocks (the server also caps requests per order). */
export const SMS_RESEND_SECONDS = 60;

export const digitsOf = (value: string): string => String(value ?? "").replace(/\D/g, "");

export function topupAmountError(amount: number, min = MIN_TOPUP, max = MAX_TOPUP): TranslationKey | null {
  if (!Number.isFinite(amount) || amount <= 0) return "payments.amount.required";
  if (amount < min) return "payments.amount.min";
  if (amount > max) return "payments.amount.max";
  return null;
}

/** `8600 1234 5678 9012` while typing (at most 19 digits). */
export function formatCardNumber(value: string): string {
  return digitsOf(value).slice(0, 19).replace(/(\d{4})(?=\d)/g, "$1 ");
}

export function cardNumberError(value: string): TranslationKey | null {
  const d = digitsOf(value);
  if (d.length === 0) return "payments.card.err.numberRequired";
  if (d.length < 16) return "payments.card.err.numberShort";
  if (d.length > 19) return "payments.card.err.numberLong";
  return null;
}

/** `12/27` while typing. */
export function formatExpiry(value: string): string {
  const d = digitsOf(value).slice(0, 4);
  return d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
}

/** `MMYY` or a translation key; a card is valid through the last day of its month. */
export function parseExpiry(value: string, now: Date = new Date()): { mmyy: string } | { error: TranslationKey } {
  const d = digitsOf(value);
  if (d.length === 0) return { error: "payments.card.err.expiryRequired" };
  if (d.length !== 4) return { error: "payments.card.err.expiryFormat" };
  const month = Number(d.slice(0, 2));
  const year = 2000 + Number(d.slice(2));
  if (month < 1 || month > 12) return { error: "payments.card.err.expiryMonth" };
  if (year * 12 + (month - 1) < now.getFullYear() * 12 + now.getMonth()) {
    return { error: "payments.card.err.expiryExpired" };
  }
  return { mmyy: d };
}

/** The 9 subscriber digits typed after the fixed `+998`: `90 123 45 67`. */
export function formatPhoneLocal(value: string): string {
  let d = digitsOf(value);
  if (d.startsWith("998") && d.length > 9) d = d.slice(3);
  d = d.slice(0, 9);
  return [d.slice(0, 2), d.slice(2, 5), d.slice(5, 7), d.slice(7, 9)].filter(Boolean).join(" ");
}

/** Click's `phone_number`: `998` + 9 digits. */
export function normalizePhone(value: string): string | null {
  const d = digitsOf(value);
  if (d.length === 9) return `998${d}`;
  return /^998\d{9}$/.test(d) ? d : null;
}

export function phoneError(value: string): TranslationKey | null {
  if (digitsOf(value).length === 0) return "payments.phone.err.required";
  return normalizePhone(value) ? null : "payments.phone.err.format";
}

export function smsCodeError(value: string): TranslationKey | null {
  const d = digitsOf(value);
  if (d.length === 0) return "payments.card.err.smsRequired";
  return d.length >= 4 && d.length <= 8 ? null : "payments.card.err.smsFormat";
}

/**
 * Opens the Click deeplink (`my.click.uz/services/pay`). Inside Telegram the
 * webview must not navigate to it (the Mini App would be lost):
 * `Telegram.WebApp.openLink` hands it to the system / the Click app.
 */
export function openClickApp(url: string): void {
  const tg = window.Telegram?.WebApp;
  if (tg?.openLink) tg.openLink(url);
  else window.location.assign(url);
}
