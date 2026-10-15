import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2 } from "lucide-react";

import { getOrder } from "../../api/payments";
import { useLocale } from "../../i18n/useLocale";
import { useT } from "../../i18n/useT";
import { primaryBtn, textBtn } from "./shared";

/** Waiting for Click's Shop API Complete: first check, its ceiling and the whole budget (ms). */
export const WAIT_POLL_START_MS = 2_000;
export const WAIT_POLL_MAX_MS = 10_000;
export const WAIT_POLL_BUDGET_MS = 300_000;

export type WaitSource = "card" | "phone" | "app";
export type WaitPhase = "polling" | "paid" | "cancelled" | "stalled";

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("aborted", "AbortError"));
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}

/**
 * Polls the order until it is paid or cancelled; the interval grows 2 s -> 10 s
 * for 5 minutes, then `stalled` + a manual recheck. Paid refreshes the wallet.
 */
function useOrderWatch(orderId: string, initial: WaitPhase = "polling") {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<WaitPhase>(initial);
  const [pollKey, setPollKey] = useState(0);

  useEffect(() => {
    if (initial === "paid") void queryClient.invalidateQueries({ queryKey: ["wallet"] });
  }, [initial, queryClient]);

  useEffect(() => {
    if (initial === "paid") return;
    const ctrl = new AbortController();
    setPhase("polling");
    void (async () => {
      let wait = pollKey > 0 ? 0 : WAIT_POLL_START_MS;
      let delay = WAIT_POLL_START_MS;
      let spent = 0;
      while (spent + wait <= WAIT_POLL_BUDGET_MS) {
        await sleep(wait, ctrl.signal);
        spent += wait;
        wait = delay;
        delay = Math.min(WAIT_POLL_MAX_MS, Math.round(delay * 1.5));
        let state: string | undefined;
        try {
          state = (await getOrder(orderId)).state;
        } catch {
          // Transient (network, 5xx): asked again on the next turn.
          if (ctrl.signal.aborted) return;
          continue;
        }
        if (ctrl.signal.aborted) return;
        if (state === "paid") {
          void queryClient.invalidateQueries({ queryKey: ["wallet"] });
          setPhase("paid");
          return;
        }
        if (state === "cancelled") {
          setPhase("cancelled");
          return;
        }
      }
      setPhase("stalled");
    })().catch((e: unknown) => {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setPhase("stalled");
    });
    return () => ctrl.abort();
  }, [orderId, initial, pollKey, queryClient]);

  const recheck = useCallback(() => setPollKey((k) => k + 1), []);
  return { phase, recheck };
}

const TEXT = {
  card: { title: "payments.wait.cardTitle", body: "payments.wait.cardBody" },
  phone: { title: "payments.wait.phoneTitle", body: "payments.wait.phoneBody" },
  app: { title: "payments.wait.appTitle", body: "payments.wait.appBody" },
} as const;

export default function WaitStep({
  orderId,
  amount,
  source,
  initial = "polling",
  onBack,
  onDone,
  onReopen,
}: {
  orderId: string;
  amount: number;
  source: WaitSource;
  initial?: "polling" | "paid";
  onBack: () => void;
  onDone: () => void;
  onReopen?: () => void;
}) {
  const t = useT();
  const { formatMoney } = useLocale();
  const { phase, recheck } = useOrderWatch(orderId, initial);

  if (phase === "paid") {
    return (
      <div role="status" className="py-4 text-center">
        <CheckCircle2 aria-hidden className="mx-auto mb-3 h-12 w-12 text-success" />
        <h3 className="mb-1 text-lg font-bold text-text">{t("payments.wait.paidTitle")}</h3>
        <p className="mb-5 text-sm text-muted">{t("payments.wait.paidBody", { amount: formatMoney(amount) })}</p>
        <button type="button" className={primaryBtn} onClick={onDone}>
          {t("payments.close")}
        </button>
      </div>
    );
  }

  if (phase === "cancelled") {
    return (
      <div role="alert" className="py-4 text-center">
        <h3 className="mb-1 text-lg font-bold text-danger">{t("payments.wait.cancelledTitle")}</h3>
        <p className="mb-5 text-sm text-muted">{t("payments.wait.cancelledBody")}</p>
        <button type="button" className={primaryBtn} onClick={onBack}>
          {t("payments.back")}
        </button>
      </div>
    );
  }

  const text = TEXT[source];
  return (
    <div role="status" aria-live="polite" className="py-4 text-center">
      {phase === "polling" && (
        <Loader2 aria-hidden className="mx-auto mb-3 h-10 w-10 animate-spin text-primary motion-reduce:animate-none" />
      )}
      <h3 className="mb-1 text-lg font-bold text-text">
        {t(phase === "stalled" ? "payments.wait.stalledTitle" : text.title)}
      </h3>
      <p className="mb-5 text-sm text-muted">{t(phase === "stalled" ? "payments.wait.stalledBody" : text.body)}</p>
      {phase === "stalled" && (
        <button type="button" className={primaryBtn} onClick={recheck}>
          {t("payments.wait.recheck")}
        </button>
      )}
      {source === "app" && onReopen && (
        <button type="button" className={`${textBtn} mt-2`} onClick={onReopen}>
          {t("payments.wait.reopen")}
        </button>
      )}
      <div className="mt-1">
        <button type="button" className={textBtn} onClick={onBack}>
          {t("payments.back")}
        </button>
      </div>
    </div>
  );
}
