import { Copy, ExternalLink } from "lucide-react";

import type { PaynetInfo } from "../../api/payments";
import useToast from "../../hooks/useToast";
import { useT } from "../../i18n/useT";
import { copyToClipboard } from "../../lib/share";

/**
 * Wallet card for paying at a Paynet agent (app, terminal, kiosk). Nothing is
 * created or credited from here: the user enters the payer id `vk-<id>` at the
 * agent and Paynet's provider call (`POST /api/payments/paynet`) credits the
 * wallet. Rendered only while the server reports Paynet as configured.
 */
export default function PaynetCard({ info, bonusPercent }: { info: PaynetInfo; bonusPercent: number }) {
  const t = useT();
  const toast = useToast();
  if (!info.enabled || !info.payer_id) return null;
  const payerId = info.payer_id;

  async function copyId() {
    if (await copyToClipboard(payerId)) toast.success(t("payments.paynet.copied"));
  }

  const steps = [t("payments.paynet.step1"), t("payments.paynet.step2"), t("payments.paynet.step3")];

  return (
    <section className="card p-4">
      <h3 className="text-sm font-semibold text-text">💳 {t("payments.paynet.title")}</h3>
      <p className="mt-1 text-xs text-muted">{t("payments.paynet.intro")}</p>
      {bonusPercent > 0 && (
        <p className="mt-2 rounded-xl bg-success/10 px-3 py-2 text-[13px] font-medium text-success">
          🎁 {t("payments.topup.bonusHint", { percent: bonusPercent })}
        </p>
      )}

      <p className="mb-1.5 mt-3 text-xs font-medium text-muted">{t("payments.paynet.idLabel")}</p>
      <button
        type="button"
        className="tap-target flex w-full items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2.5 text-left"
        onClick={() => void copyId()}
      >
        <span className="min-w-0 flex-1 truncate font-mono text-sm font-semibold tabular-nums text-text">
          {payerId}
        </span>
        <span className="flex shrink-0 items-center gap-1 rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
          <Copy aria-hidden size={12} />
          {t("common.copy")}
        </span>
      </button>

      <ol className="mt-3 space-y-1.5">
        {steps.map((step, index) => (
          <li key={step} className="flex items-start gap-2 text-[13px] text-text">
            <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[11px] font-bold text-primary">
              {index + 1}
            </span>
            <span className="min-w-0">{step}</span>
          </li>
        ))}
      </ol>

      {info.app_url && (
        <a
          href={info.app_url}
          target="_blank"
          rel="noopener noreferrer"
          className="tap-target mt-3 flex w-full items-center justify-center gap-2 rounded-2xl border border-border px-4 py-3 text-sm font-semibold text-primary"
        >
          <ExternalLink aria-hidden size={16} />
          {t("payments.paynet.open")}
        </a>
      )}
    </section>
  );
}
