import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import ReferralCard from "../components/Referral/ReferralCard";

type WalletData = { balance: number; is_pro: boolean; pro_price: number; referral_reward: number };

export default function Referral() {
  const referral = useQuery({
    queryKey: ["referral"],
    queryFn: async () => {
      const { data } = await client.get<{
        ref_link: string;
        ref_count: number;
        referrals: Array<{ first_name: string; date: number; username: string | null }>;
      }>("/referral");
      return data;
    }
  });

  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: async () => {
      const { data } = await client.get<WalletData>("/wallet");
      return data;
    },
    retry: false,
  });

  if (!referral.data) {
    return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  }

  const reward = wallet.data?.referral_reward ?? 2000;
  const totalEarned = (referral.data.ref_count ?? 0) * reward;

  return (
    <div className="space-y-4">
      <ReferralCard refLink={referral.data.ref_link} count={referral.data.ref_count} reward={reward} />

      {/* Stats */}
      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Referral daromad</h3>
        <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl bg-emerald-50 p-3 text-center">
            <p className="text-2xl font-bold text-emerald-700">{referral.data.ref_count}</p>
            <p className="text-xs text-slate-500 mt-0.5">Taklif qilinganlar</p>
          </div>
          <div className="rounded-xl bg-amber-50 p-3 text-center">
            <p className="text-2xl font-bold text-amber-700">{totalEarned.toLocaleString("uz-UZ")}</p>
            <p className="text-xs text-slate-500 mt-0.5">Jami daromad (so'm)</p>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="font-semibold text-sm text-slate-800">Taklif qilinganlar</h3>
        {referral.data.referrals.length === 0 && (
          <p className="mt-2 text-sm text-slate-500">Hali hech kim qo'shilmagan. Havolangizni ulashing.</p>
        )}
        <ul className="mt-2 space-y-2">
          {referral.data.referrals.map((user, idx) => (
            <li key={`${user.first_name}-${idx}`} className="flex items-center justify-between rounded-xl bg-slate-50 p-2 text-sm">
              <span>{user.first_name}{user.username ? ` (@${user.username})` : ""}</span>
              <span className="text-slate-500">{new Date(user.date * 1000).toLocaleDateString("ru-RU")}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

