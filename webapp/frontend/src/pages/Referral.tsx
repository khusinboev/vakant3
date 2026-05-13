import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import ReferralCard from "../components/Referral/ReferralCard";

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

  if (!referral.data) {
    return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  }

  return (
    <div className="space-y-4">
      <ReferralCard refLink={referral.data.ref_link} count={referral.data.ref_count} />
      <section className="card p-4">
        <h3 className="font-semibold">Taklif qilinganlar</h3>
        {referral.data.referrals.length === 0 && <p className="mt-2 text-sm text-slate-500">Hali hech kim qo'shilmagan. Havolangizni ulashing.</p>}
        <ul className="mt-2 space-y-2">
          {referral.data.referrals.map((user, idx) => (
            <li key={`${user.first_name}-${idx}`} className="flex items-center justify-between rounded-xl bg-slate-50 p-2 text-sm">
              <span>{user.first_name}</span>
              <span className="text-slate-500">{new Date(user.date * 1000).toLocaleDateString("ru-RU")}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
