import { useId, useState, type FormEvent } from "react";

import { clickInvoice } from "../../api/payments";
import { useLocale } from "../../i18n/useLocale";
import { useT } from "../../i18n/useT";
import { formatPhoneLocal, normalizePhone, phoneError } from "../../lib/clickInput";
import { fieldError, fieldLabel, inputCls, paymentErrorMessage, primaryBtn, textBtn } from "./shared";

/**
 * "Telefon raqam": an invoice for the order goes to the Click app registered on
 * this phone (+998 fixed, the user types 9 digits). The user confirms it in the
 * app; Click then calls our Shop API and `WaitStep` sees the order paid.
 */
export default function PhoneStep({
  orderId,
  amount,
  onBack,
  onSent,
}: {
  orderId: string;
  amount: number;
  onBack: () => void;
  onSent: () => void;
}) {
  const t = useT();
  const { formatMoney } = useLocale();
  const uid = useId();
  const [phone, setPhone] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const err = phoneError(phone);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError(null);
    const normalized = normalizePhone(phone);
    if (!normalized) return;
    setBusy(true);
    try {
      await clickInvoice(orderId, normalized);
      onSent();
    } catch (e2) {
      setError(paymentErrorMessage(e2, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <p className="mb-4 text-sm text-muted">{t("payments.phone.intro", { amount: formatMoney(amount) })}</p>
      <label htmlFor={`${uid}-phone`} className={fieldLabel}>
        {t("payments.phone.label")}
      </label>
      <div className="relative">
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-base tabular-nums text-muted"
        >
          +998
        </span>
        <input
          id={`${uid}-phone`}
          value={phone}
          inputMode="tel"
          autoComplete="tel-national"
          disabled={busy}
          autoFocus
          aria-invalid={touched && err !== null}
          onChange={(e) => setPhone(formatPhoneLocal(e.target.value))}
          placeholder="90 123 45 67"
          className={`${inputCls} pl-[3.75rem]`}
        />
      </div>
      {touched && err && (
        <p role="alert" className={fieldError}>
          {t(err)}
        </p>
      )}
      {error && (
        <p role="alert" className={fieldError}>
          {error}
        </p>
      )}
      <button type="submit" disabled={busy} className={`${primaryBtn} mt-4`}>
        {busy ? t("payments.card.sending") : t("payments.phone.send")}
      </button>
      <div className="mt-2">
        <button type="button" disabled={busy} className={textBtn} onClick={onBack}>
          {t("payments.back")}
        </button>
      </div>
    </form>
  );
}
