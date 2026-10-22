import { useEffect, useId, useState, type FormEvent } from "react";
import { Lock } from "lucide-react";

import { clickCardConfirm, clickCardStart } from "../../api/payments";
import { useLocale } from "../../i18n/useLocale";
import { useT } from "../../i18n/useT";
import { parseApiError } from "../../lib/parseApiError";
import {
  SMS_RESEND_SECONDS,
  cardNumberError,
  digitsOf,
  formatCardNumber,
  formatExpiry,
  parseExpiry,
  smsCodeError,
} from "../../lib/clickInput";
import { fieldError, fieldLabel, inputCls, paymentErrorMessage, primaryBtn, textBtn } from "./shared";

/**
 * "Karta": Click one-time card token + SMS confirmation. The card number,
 * expiry and code live ONLY in this component's state (no store, no storage,
 * no URL) and disappear when it unmounts. The balance is credited by Click's
 * Shop API; afterwards the sheet waits for the order (`WaitStep`).
 */
export default function CardStep({
  orderId,
  amount,
  stage,
  onStage,
  onBack,
  onSubmitted,
}: {
  orderId: string;
  amount: number;
  /** Lifted so the Telegram BackButton can step from "sms" back to "form". */
  stage: "form" | "sms";
  onStage: (stage: "form" | "sms") => void;
  onBack: () => void;
  onSubmitted: (status: "paid" | "pending") => void;
}) {
  const t = useT();
  const { formatMoney } = useLocale();
  const uid = useId();
  const [number, setNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [sms, setSms] = useState("");
  const [phoneMasked, setPhoneMasked] = useState("");
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useState(0);

  useEffect(() => {
    if (stage !== "sms" || resendIn <= 0) return;
    const timer = window.setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [stage, resendIn]);

  const numberErr = cardNumberError(number);
  const exp = parseExpiry(expiry);
  const expiryErr = "error" in exp ? exp.error : null;
  const smsErr = smsCodeError(sms);

  async function requestCode(isResend: boolean) {
    if (!("mmyy" in exp)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const r = await clickCardStart(orderId, digitsOf(number), exp.mmyy);
      setPhoneMasked(r.phone_masked);
      setSms("");
      setTouched(false);
      setResendIn(SMS_RESEND_SECONDS);
      if (isResend) setNotice(t("payments.card.newCode"));
      onStage("sms");
    } catch (err) {
      setError(paymentErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  }

  function sendCode(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError(null);
    if (numberErr || expiryErr) return;
    void requestCode(false);
  }

  async function confirm(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    setError(null);
    if (smsErr) return;
    setBusy(true);
    try {
      const r = await clickCardConfirm(orderId, digitsOf(sms));
      if (r.status === "cancelled") {
        setError(t("payments.card.cancelled"));
        return;
      }
      setNumber("");
      setExpiry("");
      setSms("");
      onSubmitted(r.status);
    } catch (err) {
      setError(paymentErrorMessage(err, t));
      // The one-time token is gone (spent, expired, never issued): start over from the card.
      if (parseApiError(err).code === "CARD_TOKEN_MISSING") {
        onStage("form");
        setSms("");
        setTouched(false);
      }
    } finally {
      setBusy(false);
    }
  }

  const amountText = formatMoney(amount);

  if (stage === "sms") {
    return (
      <form onSubmit={confirm} noValidate>
        <p className="mb-4 text-sm text-muted">
          {phoneMasked
            ? t("payments.card.smsIntro", { phone: phoneMasked, amount: amountText })
            : t("payments.card.smsIntroNoPhone", { amount: amountText })}
        </p>
        <label htmlFor={`${uid}-sms`} className={fieldLabel}>
          {t("payments.card.sms")}
        </label>
        <input
          id={`${uid}-sms`}
          value={sms}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={8}
          disabled={busy}
          autoFocus
          aria-invalid={touched && smsErr !== null}
          onChange={(e) => setSms(digitsOf(e.target.value).slice(0, 8))}
          placeholder="••••••"
          className={`${inputCls} text-center text-lg tracking-[0.4em]`}
        />
        {touched && smsErr && (
          <p role="alert" className={fieldError}>
            {t(smsErr)}
          </p>
        )}
        {error && (
          <p role="alert" className={fieldError}>
            {error}
          </p>
        )}
        {notice && !error && (
          <p role="status" className="mt-2 text-[13px] text-muted">
            {notice}
          </p>
        )}
        <button type="submit" disabled={busy} className={`${primaryBtn} mt-4`}>
          {busy ? t("payments.card.paying") : t("payments.card.pay", { amount: amountText })}
        </button>
        <button
          type="button"
          disabled={busy || resendIn > 0}
          className={`${textBtn} mt-2 w-full`}
          onClick={() => void requestCode(true)}
        >
          {resendIn > 0 ? t("payments.card.resendIn", { seconds: resendIn }) : t("payments.card.resend")}
        </button>
        <div className="mt-2 flex justify-between">
          <button
            type="button"
            disabled={busy}
            className={textBtn}
            onClick={() => {
              onStage("form");
              setError(null);
              setNotice(null);
              setSms("");
            }}
          >
            {t("payments.card.change")}
          </button>
          <button type="button" disabled={busy} className={textBtn} onClick={onBack}>
            {t("payments.back")}
          </button>
        </div>
      </form>
    );
  }

  return (
    <form onSubmit={sendCode} noValidate>
      <label htmlFor={`${uid}-number`} className={fieldLabel}>
        {t("payments.card.number")}
      </label>
      <input
        id={`${uid}-number`}
        value={number}
        inputMode="numeric"
        autoComplete="cc-number"
        disabled={busy}
        autoFocus
        aria-invalid={touched && numberErr !== null}
        onChange={(e) => setNumber(formatCardNumber(e.target.value))}
        placeholder="8600 0000 0000 0000"
        className={inputCls}
      />
      {touched && numberErr && (
        <p role="alert" className={fieldError}>
          {t(numberErr)}
        </p>
      )}

      <label htmlFor={`${uid}-exp`} className={`${fieldLabel} mt-3`}>
        {t("payments.card.expiry")}
      </label>
      <input
        id={`${uid}-exp`}
        value={expiry}
        inputMode="numeric"
        autoComplete="cc-exp"
        disabled={busy}
        aria-invalid={touched && expiryErr !== null}
        onChange={(e) => setExpiry(formatExpiry(e.target.value))}
        placeholder={t("payments.card.expiryPlaceholder")}
        maxLength={5}
        className={`${inputCls} max-w-40`}
      />
      {touched && expiryErr && (
        <p role="alert" className={fieldError}>
          {t(expiryErr)}
        </p>
      )}

      <p className="mt-3 flex items-start gap-1.5 text-[13px] text-muted">
        <Lock aria-hidden size={14} className="mt-0.5 shrink-0" />
        {t("payments.card.secure")}
      </p>

      {error && (
        <p role="alert" className={fieldError}>
          {error}
        </p>
      )}
      <button type="submit" disabled={busy} className={`${primaryBtn} mt-4`}>
        {busy ? t("payments.card.sending") : t("payments.card.getCode")}
      </button>
      <div className="mt-2">
        <button type="button" disabled={busy} className={textBtn} onClick={onBack}>
          {t("payments.back")}
        </button>
      </div>
    </form>
  );
}
