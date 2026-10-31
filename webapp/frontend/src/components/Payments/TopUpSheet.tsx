import { useEffect, useId, useRef, useState } from "react";
import { ChevronRight, CreditCard, Phone, Smartphone, Store, type LucideIcon } from "lucide-react";

import { createOrder, type ClickMethod, type PaymentsConfig, type PaynetInfo } from "../../api/payments";
import BottomSheet from "../ui/BottomSheet";
import { clearBackInterceptor, setBackInterceptor } from "../../hooks/useBackInterceptor";
import { useLocale } from "../../i18n/useLocale";
import { useT } from "../../i18n/useT";
import type { TranslationKey } from "../../i18n";
import { DEFAULT_TOPUP, TOPUP_PRESETS, openClickApp, topupAmountError } from "../../lib/clickInput";
import CardStep from "./CardStep";
import PaynetCard from "./PaynetCard";
import PhoneStep from "./PhoneStep";
import WaitStep, { type WaitSource } from "./WaitStep";
import { fieldError, inputCls, paymentErrorMessage, textBtn } from "./shared";

type View = "home" | "card" | "phone" | "wait" | "paynet";
type Order = { id: string; amount: number; method: ClickMethod; checkoutUrl: string };

const TITLES: Record<View, TranslationKey> = {
  home: "payments.topup.title",
  card: "payments.card.title",
  phone: "payments.phone.title",
  wait: "payments.wait.title",
  paynet: "payments.paynet.title",
};

/** Longest typed amount: 10 000 000 has 8 digits; one spare lets the error show. */
const MAX_DIGITS = 9;

/**
 * Wallet top-up (port of SlaydX `PayDialog`): free amount, then one of three
 * Click methods — card (our form: one-time token + SMS), phone (invoice to the
 * Click app), Click app (deeplink via `Telegram.WebApp.openLink`); the Click
 * page stays as a fallback link. Below them sits «Paynet» (when configured):
 * it opens the payer id with the steps, nothing is created there. This sheet
 * NEVER credits: it creates an order, starts the payment and waits for the
 * order (credited by Click's Shop API); Paynet credits through its own provider
 * call. With Click off and Paynet on, the sheet opens straight on the Paynet view.
 *
 * Back (Telegram BackButton, Esc, backdrop): one level at a time — SMS step ->
 * card form -> method choice -> closed.
 */
export default function TopUpSheet({
  open,
  onClose,
  config,
  paynet,
}: {
  open: boolean;
  onClose: () => void;
  /** Null while Click is not configured; then only Paynet can be offered. */
  config: PaymentsConfig | null;
  paynet?: PaynetInfo | null;
}) {
  const t = useT();
  const { formatMoney, formatNumber } = useLocale();
  const amountId = useId();
  const [amount, setAmount] = useState<number>(DEFAULT_TOPUP);
  const [amountTouched, setAmountTouched] = useState(false);
  const [view, setView] = useState<View>("home");
  const [cardStage, setCardStage] = useState<"form" | "sms">("form");
  const [order, setOrder] = useState<Order | null>(null);
  const [source, setSource] = useState<WaitSource>("card");
  const [waitInitial, setWaitInitial] = useState<"polling" | "paid">("polling");
  const [busy, setBusy] = useState<ClickMethod | null>(null);
  const [error, setError] = useState<string | null>(null);

  const paynetOn = Boolean(paynet?.enabled && paynet.payer_id);
  const firstView: View = config ? "home" : "paynet";

  // Every opening starts clean (card details live in the unmounted step).
  useEffect(() => {
    if (!open) return;
    setError(null);
    setBusy(null);
    setView(firstView);
    setCardStage("form");
    setOrder(null);
    setWaitInitial("polling");
  }, [open, firstView]);

  const back = () => {
    setError(null);
    if (view === "card" && cardStage === "sms") {
      setCardStage("form");
      return;
    }
    if (view !== firstView) {
      setView(firstView);
      setCardStage("form");
      return;
    }
    onClose();
  };

  // Telegram's BackButton goes one level back instead of leaving the page.
  const backRef = useRef(back);
  useEffect(() => {
    backRef.current = back;
  });
  useEffect(() => {
    if (!open) return;
    setBackInterceptor(() => {
      backRef.current();
      return true;
    });
    return () => clearBackInterceptor();
  }, [open]);

  const minAmount = config?.min_amount ?? 0;
  const maxAmount = config?.max_amount ?? 0;
  const amountErrKey = config ? topupAmountError(amount, minAmount, maxAmount) : null;
  const amountErr = amountErrKey
    ? t(amountErrKey, { min: formatNumber(minAmount), max: formatNumber(maxAmount) })
    : null;
  const showAmountErr = amountErr !== null && (amount > 0 || amountTouched);

  /** One order per (amount, method); reused while neither changes. */
  async function ensureOrder(method: ClickMethod): Promise<Order> {
    if (order && order.amount === amount && order.method === method) return order;
    const r = await createOrder(amount, method);
    const next = { id: r.order.id, amount: r.order.amount, method, checkoutUrl: r.checkout_url };
    setOrder(next);
    return next;
  }

  async function start(method: ClickMethod) {
    if (!config || amountErrKey || busy) return;
    setError(null);
    setBusy(method);
    try {
      const o = await ensureOrder(method);
      if (method === "card") {
        setCardStage("form");
        setView("card");
      } else if (method === "phone") {
        setView("phone");
      } else {
        // `app` and the `page` fallback: the same my.click.uz link, opened outside the webview.
        openClickApp(o.checkoutUrl);
        setSource("app");
        setWaitInitial("polling");
        setView("wait");
      }
    } catch (e) {
      setError(paymentErrorMessage(e, t));
    } finally {
      setBusy(null);
    }
  }

  return (
    <BottomSheet open={open} onClose={back} title={t(TITLES[view])} maxHeightClass="max-h-[90dvh]">
      {view === "card" && order && (
        <CardStep
          orderId={order.id}
          amount={order.amount}
          stage={cardStage}
          onStage={setCardStage}
          onBack={back}
          onSubmitted={(status) => {
            setSource("card");
            setWaitInitial(status === "paid" ? "paid" : "polling");
            setView("wait");
          }}
        />
      )}

      {view === "phone" && order && (
        <PhoneStep
          orderId={order.id}
          amount={order.amount}
          onBack={back}
          onSent={() => {
            setSource("phone");
            setWaitInitial("polling");
            setView("wait");
          }}
        />
      )}

      {view === "wait" && order && (
        <WaitStep
          orderId={order.id}
          amount={order.amount}
          source={source}
          initial={waitInitial}
          onBack={back}
          onDone={onClose}
          onReopen={source === "app" ? () => openClickApp(order.checkoutUrl) : undefined}
        />
      )}

      {view === "paynet" && paynet && (
        <PaynetCard info={paynet} bonusPercent={config?.bonus_percent ?? 0} />
      )}

      {view === "home" && config && (
        <>
          <p className="mb-4 text-sm text-muted">{t("payments.topup.intro")}</p>
          {config.bonus_percent > 0 && (
            <p className="mb-3 rounded-xl bg-success/10 px-3 py-2 text-[13px] font-medium text-success">
              🎁 {t("payments.topup.bonusHint", { percent: config.bonus_percent })}
            </p>
          )}

          <fieldset className="mb-4">
            <legend className="mb-2 text-sm font-semibold text-text">{t("payments.amount.label")}</legend>
            <div className="grid grid-cols-2 gap-2">
              {TOPUP_PRESETS.map((value) => {
                const on = amount === value;
                const best = value === DEFAULT_TOPUP;
                return (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setAmount(value)}
                    className={`tap-target flex min-h-14 flex-col items-center justify-center rounded-xl border px-2 py-2 tabular-nums ${
                      on ? "border-primary bg-primary/10" : "border-border bg-surface"
                    }`}
                  >
                    <span className="text-base font-bold text-text">{formatNumber(value)}</span>
                    <span className={`text-xs ${best ? "font-semibold text-primary" : "text-muted"}`}>
                      {best ? t("payments.amount.best") : t("payments.amount.unit")}
                    </span>
                  </button>
                );
              })}
            </div>
            <label htmlFor={amountId} className="mb-1.5 mt-3 block text-sm font-medium text-muted">
              {t("payments.amount.other")}
            </label>
            <div className="relative">
              <input
                id={amountId}
                type="text"
                inputMode="numeric"
                autoComplete="off"
                enterKeyHint="done"
                placeholder={formatNumber(DEFAULT_TOPUP)}
                value={amount > 0 ? formatNumber(amount) : ""}
                aria-invalid={showAmountErr}
                onChange={(e) => {
                  const digits = e.target.value.replace(/\D/g, "").slice(0, MAX_DIGITS);
                  setAmount(digits ? Number(digits) : 0);
                }}
                onBlur={() => setAmountTouched(true)}
                className={`${inputCls} pr-14`}
              />
              <span
                aria-hidden
                className="pointer-events-none absolute inset-y-0 right-3.5 flex items-center text-sm text-muted"
              >
                {t("payments.amount.unit")}
              </span>
            </div>
            {showAmountErr ? (
              <p role="alert" className={fieldError}>
                {amountErr}
              </p>
            ) : (
              <p className="mt-1.5 text-[13px] text-muted">
                {t("payments.amount.range", {
                  min: formatNumber(minAmount),
                  max: formatNumber(maxAmount),
                })}
              </p>
            )}
          </fieldset>

          <p className="mb-2 text-sm font-semibold text-text">{t("payments.method.label")}</p>
          <div className="flex flex-col gap-2">
            <MethodRow
              icon={CreditCard}
              title={t("payments.method.card")}
              hint={t("payments.method.cardHint")}
              loading={busy === "card"}
              loadingText={t("payments.opening")}
              disabled={busy !== null || amountErrKey !== null}
              onClick={() => void start("card")}
            />
            <MethodRow
              icon={Phone}
              title={t("payments.method.phone")}
              hint={t("payments.method.phoneHint")}
              loading={busy === "phone"}
              loadingText={t("payments.opening")}
              disabled={busy !== null || amountErrKey !== null}
              onClick={() => void start("phone")}
            />
            <MethodRow
              icon={Smartphone}
              title={t("payments.method.app")}
              hint={t("payments.method.appHint")}
              loading={busy === "app"}
              loadingText={t("payments.opening")}
              disabled={busy !== null || amountErrKey !== null}
              onClick={() => void start("app")}
            />
            {paynetOn && (
              <MethodRow
                icon={Store}
                title={t("payments.method.paynet")}
                hint={t("payments.method.paynetHint")}
                loading={false}
                loadingText=""
                disabled={busy !== null}
                onClick={() => {
                  setError(null);
                  setView("paynet");
                }}
              />
            )}
          </div>
          <div className="mt-1 flex justify-center">
            <button
              type="button"
              disabled={busy !== null || amountErrKey !== null}
              className={`${textBtn} text-[13px] underline`}
              onClick={() => void start("page")}
            >
              {busy === "page" ? t("payments.opening") : t("payments.method.page")}
            </button>
          </div>

          <p className="mt-3 text-center text-[13px] tabular-nums text-muted">
            {t("payments.total")}{" "}
            <span className="font-semibold text-text">{amountErrKey ? "—" : formatMoney(amount)}</span>
          </p>
          {error && (
            <p role="alert" className="mt-3 text-[13px] text-danger">
              {error}
            </p>
          )}
        </>
      )}
    </BottomSheet>
  );
}

function MethodRow({
  icon: Icon,
  title,
  hint,
  loading,
  loadingText,
  disabled,
  onClick,
}: {
  icon: LucideIcon;
  title: string;
  hint: string;
  loading: boolean;
  loadingText: string;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="tap-target flex min-h-14 w-full items-center gap-3 rounded-xl border border-border bg-surface px-3.5 py-2 text-left disabled:opacity-50"
    >
      <Icon aria-hidden size={20} className="shrink-0 text-primary" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-text">{loading ? loadingText : title}</span>
        <span className="block text-xs text-muted">{hint}</span>
      </span>
      <ChevronRight aria-hidden size={16} className="shrink-0 text-muted" />
    </button>
  );
}
