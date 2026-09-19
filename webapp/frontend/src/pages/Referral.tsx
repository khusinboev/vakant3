import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import ReferralCard from "../components/Referral/ReferralCard";
import { useT } from "../i18n/useT";
import { useLocale } from "../i18n/useLocale";

type WalletData = { balance: number; is_pro: boolean; pro_price: number; referral_reward: number };

type ReferralData = {
  ref_link: string;
  ref_count: number;
  referrals: Array<{ first_name: string | null; date: number; username: string | null }>;
};

export default function Referral() {
  const t = useT();
  const { formatNumber, formatDate } = useLocale();

  const referral = useQuery<ReferralData>({
    queryKey: ["referral"],
    queryFn: async () => {
      const { data } = await client.get<ReferralData>("/referral");
      return data;
    },
  });

  const wallet = useQuery<WalletData>({
    queryKey: ["wallet"],
    queryFn: async () => {
      const { data } = await client.get<WalletData>("/wallet");
      return data;
    },
    retry: false,
  });

  if (referral.isLoading) {
    return <div className="card p-4 text-sm text-muted">{t("common.loading")}</div>;
  }

  if (referral.isError || !referral.data) {
    return <div className="card p-4 text-sm text-danger">{t("referral.loadError")}</div>;
  }

  const reward = wallet.data?.referral_reward ?? 2000;
  const totalEarned = (referral.data.ref_count ?? 0) * reward;

  return (
    <div className="space-y-4">
      <ReferralCard refLink={referral.data.ref_link} count={referral.data.ref_count} reward={reward} />

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-text">{t("referral.income")}</h3>
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl bg-success/10 p-3 text-center">
            <p className="text-2xl font-bold text-success">{referral.data.ref_count}</p>
            <p className="mt-0.5 text-xs text-muted">{t("referral.invited")}</p>
          </div>
          <div className="rounded-xl bg-warning/10 p-3 text-center">
            <p className="text-2xl font-bold text-warning">{formatNumber(totalEarned)}</p>
            <p className="mt-0.5 text-xs text-muted">{t("referral.totalEarned")}</p>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-text">{t("referral.invited")}</h3>
        {referral.data.referrals.length === 0 && (
          <p className="mt-2 text-sm text-muted">{t("referral.emptyList")}</p>
        )}
        <ul className="mt-2 space-y-2">
          {referral.data.referrals.map((user, idx) => (
            <li
              key={`${user.username ?? user.first_name ?? "user"}-${idx}`}
              className="flex items-center justify-between gap-3 rounded-xl bg-surfaceAlt p-2 text-sm text-text"
            >
              <span className="min-w-0 truncate">
                {user.first_name || t("referral.anonymous")}
                {user.username ? ` (@${user.username})` : ""}
              </span>
              <span className="shrink-0 text-muted">{formatDate(user.date)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
