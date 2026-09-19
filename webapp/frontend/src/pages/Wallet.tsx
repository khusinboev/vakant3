import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Crown, Link as LinkIcon, Wallet } from "lucide-react";
import { useNavigate } from "react-router-dom";

import client from "../api/client";
import useToast from "../hooks/useToast";
import { useT } from "../i18n/useT";
import { useLocale } from "../i18n/useLocale";
import { ADMIN_USERNAME, BOT_USERNAME, openTelegramLink } from "../lib/constants";
import { copyToClipboard, shareRefLink } from "../lib/share";
import { useAuthStore } from "../store/auth";

type WalletData = {
  balance: number;
  is_pro: boolean;
  pro_price: number;
  referral_reward: number;
};

export default function WalletPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const t = useT();
  const { formatMoney, formatNumber } = useLocale();
  const toast = useToast();
  const authUser = useAuthStore((s) => s.user);

  const wallet = useQuery<WalletData>({
    queryKey: ["wallet"],
    queryFn: async () => {
      const { data } = await client.get<WalletData>("/wallet");
      return data;
    },
  });

  const activatePro = useMutation({
    mutationFn: async () => {
      const { data } = await client.post<{ ok: boolean; balance: number; is_pro: boolean }>("/wallet/activate-pro");
      return data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData<WalletData>(["wallet"], (prev) =>
        prev ? { ...prev, balance: data.balance, is_pro: data.is_pro } : prev,
      );
      toast.success(t("wallet.activated"));
    },
    onError: (error) => toast.apiError(error),
  });

  const w = wallet.data;

  const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
  const refUserId = tgUser?.id ?? authUser?.user_id;
  const refLink = refUserId ? `https://t.me/${BOT_USERNAME}?start=ref_${refUserId}` : null;

  async function copyRef() {
    if (refLink && (await copyToClipboard(refLink))) toast.success(t("referral.copied"));
  }

  if (wallet.isLoading) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted">
        {t("common.loading")}
      </div>
    );
  }

  if (!w) {
    return <div className="card p-6 text-center text-sm text-muted">{t("wallet.notFound")}</div>;
  }

  const refLinkRow = refLink && (
    <div className="mb-3 flex gap-2">
      <button
        type="button"
        className="tap-target flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs font-medium text-text"
        onClick={() => void copyRef()}
        title={refLink}
      >
        <LinkIcon size={14} className="shrink-0 text-primary" />
        <span className="min-w-0 flex-1 truncate font-mono text-[11px]">{refLink}</span>
        <span className="shrink-0 rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
          {t("common.copy")}
        </span>
      </button>
      <button
        type="button"
        className="tap-target flex shrink-0 items-center gap-1 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primaryFg"
        onClick={() => shareRefLink(refLink, t("referral.shareText"))}
      >
        📤 {t("common.shareShort")}
      </button>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Balance card */}
      <section className="card overflow-hidden p-0">
        <div className="bg-gradient-to-br from-brand-700 to-brand-900 px-5 py-6 text-white">
          <div className="flex items-center gap-2 text-sm text-white/70">
            <Wallet size={16} />
            <span>{t("wallet.balance")}</span>
          </div>
          <p className="mt-2 text-3xl font-bold tracking-tight">{formatMoney(w.balance)}</p>
          {w.is_pro ? (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-accent px-3 py-1 text-xs font-bold text-black/80">
              <Crown size={13} />
              {t("wallet.proActive")}
            </div>
          ) : (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-medium text-white/80">
              {t("wallet.freePlan")}
            </div>
          )}
        </div>
      </section>

      {/* Pro tariff quick info and activation */}
      {!w.is_pro && (
        <section className="card p-4">
          <h3 className="text-sm font-semibold text-text">💎 {t("wallet.proTitle")}</h3>
          <p className="mt-1 text-xs text-muted">{t("wallet.proDesc")}</p>
          <div className="mt-3 rounded-xl bg-surfaceAlt px-3 py-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted">{t("wallet.price")}</span>
              <span className="font-semibold text-text">{formatMoney(w.pro_price)}</span>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-muted">{t("wallet.balanceLabel")}</span>
              <span className={`font-semibold ${w.balance >= w.pro_price ? "text-success" : "text-danger"}`}>
                {formatMoney(w.balance)}
              </span>
            </div>
          </div>
          {w.balance >= w.pro_price ? (
            <button
              type="button"
              className="tap-target mt-3 w-full rounded-2xl bg-warning px-4 py-3 text-sm font-semibold text-white disabled:opacity-60 dark:text-bg"
              disabled={activatePro.isPending}
              onClick={() => activatePro.mutate()}
            >
              {activatePro.isPending ? t("wallet.activating") : t("wallet.activate")}
            </button>
          ) : (
            <p className="mt-2 text-xs text-muted">
              {t("wallet.needMore", { amount: formatNumber(w.pro_price - w.balance) })}
            </p>
          )}
        </section>
      )}

      {!w.is_pro && (
        <>
          {/* Referral earn — primary path to Pro */}
          <section className="card border-2 border-primary/40 bg-primary/5 p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-text">
              🎁 {t("wallet.referralWayTitle")}
            </h3>
            <p className="mb-3 text-sm text-text">
              {t("wallet.referralWayBody", { amount: formatNumber(w.referral_reward) })}
            </p>
            {refLinkRow}
            <p className="mt-2 text-center text-xs text-primary">
              ✓ {t("wallet.autoPro", { amount: formatNumber(w.pro_price) })}
            </p>
          </section>

          {/* Admin help — secondary option */}
          <section className="card p-4">
            <h3 className="mb-2 text-sm font-semibold text-text">💳 {t("wallet.adminTitle")}</h3>
            <p className="mb-3 text-xs text-muted">
              {t("wallet.adminBody", { amount: formatNumber(w.pro_price) })}
            </p>
            <button
              type="button"
              className="tap-target flex w-full items-center justify-center gap-2 rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-primaryFg"
              onClick={() => {
                const msg = t("wallet.adminMessage", {
                  amount: formatNumber(w.pro_price),
                  userId: tgUser?.id ?? authUser?.user_id ?? "—",
                });
                openTelegramLink(`https://t.me/${ADMIN_USERNAME}?text=${encodeURIComponent(msg)}`);
              }}
            >
              💬 {t("wallet.adminCta")}
            </button>
          </section>
        </>
      )}

      {w.is_pro && (
        <>
          <section className="card p-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={20} className="shrink-0 text-success" />
              <div>
                <p className="text-sm font-semibold text-text">{t("wallet.proActive")}</p>
                <p className="mt-0.5 text-xs text-muted">{t("wallet.proActiveBody")}</p>
              </div>
            </div>
          </section>

          <section className="card p-4">
            <h3 className="mb-2 text-sm font-semibold text-text">🎁 {t("wallet.inviteTitle")}</h3>
            <p className="mb-3 text-xs text-muted">
              {t("wallet.inviteBody", { amount: formatNumber(w.referral_reward) })}
            </p>
            {refLinkRow}
          </section>
        </>
      )}

      <section className="card p-4">
        <button
          type="button"
          className="tap-target w-full rounded-2xl border border-border px-4 py-3 text-left text-sm font-semibold text-text"
          onClick={() => navigate("/referral")}
        >
          📊 {t("wallet.refStats")} →
        </button>
      </section>
    </div>
  );
}
