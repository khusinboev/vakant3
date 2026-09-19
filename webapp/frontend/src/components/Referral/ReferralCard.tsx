import { useT } from "../../i18n/useT";
import { useLocale } from "../../i18n/useLocale";
import useToast from "../../hooks/useToast";
import { copyToClipboard, shareRefLink } from "../../lib/share";

type Props = {
  refLink: string;
  count: number;
  reward?: number;
};

export default function ReferralCard({ refLink, count, reward = 2000 }: Props) {
  const t = useT();
  const { formatNumber } = useLocale();
  const toast = useToast();

  async function copy() {
    if (await copyToClipboard(refLink)) toast.success(t("referral.copied"));
  }

  return (
    <section className="card overflow-hidden p-0">
      <div className="bg-gradient-to-br from-brand-600 to-brand-700 px-5 py-5 text-white">
        <p className="text-sm font-medium opacity-90">{t("referral.perInvite")}</p>
        <p className="mt-1 text-3xl font-bold tracking-tight">
          {t("referral.rewardAmount", { amount: formatNumber(reward) })}
        </p>
        <p className="mt-1 text-xs opacity-75">{t("referral.autoCredit")}</p>
      </div>
      <div className="p-4">
        <p className="mb-2 text-xs text-muted">{t("referral.yourLink")}</p>
        <div className="flex gap-2">
          <div className="flex-1 truncate rounded-xl border border-border bg-surfaceAlt px-3 py-2 text-xs text-text">
            {refLink}
          </div>
          <button
            type="button"
            onClick={() => void copy()}
            className="tap-target shrink-0 rounded-xl border border-border px-3 py-2 text-xs font-semibold text-text"
          >
            {t("common.copy")}
          </button>
        </div>
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-sm text-muted">{t("referral.invitedWithCount", { n: count })}</p>
          <button
            type="button"
            onClick={() => shareRefLink(refLink, t("referral.shareText"))}
            className="tap-target shrink-0 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primaryFg"
          >
            {t("common.share")}
          </button>
        </div>
      </div>
    </section>
  );
}
