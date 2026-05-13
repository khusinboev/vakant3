import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import client from "../api/client";
import ActivityChart from "../components/Profile/ActivityChart";
import FilterSummary from "../components/Profile/FilterSummary";
import StatsGrid from "../components/Profile/StatsGrid";

export default function Profile() {
  const profile = useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      const { data } = await client.get<{
        user: { first_name: string; username: string | null; photo_url: string | null };
        stats: { member_since: string; saves_count: number; referrals_count: number };
        current_filters: { specs: string | null; region: string | null; district: string | null; money: number | null };
      }>("/profile");
      return data;
    }
  });

  if (profile.isLoading) {
    return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  }

  if (profile.isError || !profile.data) {
    return <div className="card p-4 text-sm text-red-600">Profilni yuklab bo'lmadi. Qayta urinib ko'ring.</div>;
  }

  const regionText = [profile.data.current_filters.region, profile.data.current_filters.district].filter(Boolean).join(" / ");

  return (
    <div className="space-y-4">
      <section className="card flex items-center gap-3 p-4">
        <div className="h-14 w-14 overflow-hidden rounded-full bg-brand-100">
          {profile.data.user.photo_url ? <img src={profile.data.user.photo_url} alt="avatar" className="h-full w-full object-cover" /> : null}
        </div>
        <div>
          <p className="font-semibold">{profile.data.user.first_name}</p>
          <p className="text-sm text-slate-500">{profile.data.user.username ? `@${profile.data.user.username}` : "@username yo'q"}</p>
        </div>
      </section>

      <StatsGrid
        memberSince={profile.data.stats.member_since}
        savesCount={profile.data.stats.saves_count}
        referralsCount={profile.data.stats.referrals_count}
        regionText={regionText}
      />

      <FilterSummary {...profile.data.current_filters} />
      <ActivityChart savesCount={profile.data.stats.saves_count} referralsCount={profile.data.stats.referrals_count} />

      <Link to="/referral" className="tap-target inline-flex rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white">
        Referral sahifasi
      </Link>
    </div>
  );
}
