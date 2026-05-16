import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bookmark, Crown, Share2, Users, Wallet } from "lucide-react";

import client from "../api/client";
import { useSaves } from "../hooks/useSaves";
import { shareRefLink } from "../components/Referral/ReferralCard";

type WalletData = { balance: number; is_pro: boolean; pro_price: number; referral_reward: number };

function fmt(n: number) {
  return n.toLocaleString("uz-UZ");
}

export default function Profile() {
  const navigate = useNavigate();
  const webApp = window.Telegram?.WebApp;
  const initData = webApp?.initDataUnsafe;
  const user = initData?.user;

  if (!webApp) {
    return (
      <div className="card p-6 text-center">
        <p className="text-base font-semibold text-slate-700">Profil</p>
        <p className="mt-2 text-sm text-slate-500">
          Profil ma'lumotlari Telegram ichida ochilganda ko'rinadi.
        </p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="card p-6 text-center">
        <p className="text-base font-semibold text-slate-700">Profil</p>
        <p className="mt-2 text-sm text-slate-500">
          Telegram user ma'lumotlari topilmadi. WebApp tugmasi orqali qayta ochib ko'ring.
        </p>
      </div>
    );
  }

  const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");

  const saves = useSaves(1, 1, true);
  const savesCount = saves.list.data?.total ?? 0;

  const referralStats = useQuery({
    queryKey: ["referral", "stats"],
    queryFn: async () => {
      const { data } = await client.get<{ current: number; required: number; enabled: boolean; unlocked: boolean; ref_link: string }>("/referral/stats");
      return data;
    },
    retry: false,
  });

  const wallet = useQuery({
    queryKey: ["wallet"],
    queryFn: async () => {
      const { data } = await client.get<WalletData>("/wallet");
      return data;
    },
    retry: false,
  });

  const refCount = referralStats.data?.current ?? 0;
  const refLink = referralStats.data?.ref_link;
  const balance = wallet.data?.balance ?? 0;
  const isPro = wallet.data?.is_pro ?? false;

  function shareRef() {
    if (refLink) shareRefLink(refLink);
  }

  return (
    <div className="space-y-4">
      {/* Hero */}
      <section className="card overflow-hidden p-0">
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 px-5 pt-6 pb-4 text-white">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 shrink-0 overflow-hidden rounded-full border-2 border-white/20 bg-slate-700">
              {user.photo_url ? (
                <img src={user.photo_url} alt={fullName || "Avatar"} className="h-full w-full object-cover" />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-2xl font-bold text-white/70">
                  {(user.first_name?.[0] || "U").toUpperCase()}
                </div>
              )}
            </div>
            <div className="min-w-0">
              <p className="text-lg font-bold leading-tight">{fullName || "Telegram user"}</p>
              <p className="text-sm text-slate-400">{user.username ? `@${user.username}` : `ID: ${user.id}`}</p>
              <div className="mt-2">
                {isPro ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-400 px-2.5 py-0.5 text-xs font-bold text-amber-900">
                    <Crown size={11} /> PRO
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-600 px-2.5 py-0.5 text-xs font-medium text-slate-300">
                    Boshlang'ich
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 divide-x divide-slate-100 bg-white">
          <div className="flex flex-col items-center py-3 text-center">
            <p className="text-lg font-bold text-slate-900">{saves.list.isLoading ? "—" : savesCount}</p>
            <p className="text-[11px] text-slate-500">Saqlangan</p>
          </div>
          <div className="flex flex-col items-center py-3 text-center">
            <p className="text-lg font-bold text-slate-900">{referralStats.isLoading ? "—" : refCount}</p>
            <p className="text-[11px] text-slate-500">Referallar</p>
          </div>
          <div className="flex flex-col items-center py-3 text-center">
            <p className="text-lg font-bold text-slate-900">{wallet.isLoading ? "—" : `${fmt(balance)}`}</p>
            <p className="text-[11px] text-slate-500">Balans (so'm)</p>
          </div>
        </div>
      </section>

      {/* Quick actions */}
      <section className="grid grid-cols-2 gap-3">
        <button
          className="card tap-target flex flex-col items-center gap-2 p-4 text-center"
          onClick={() => navigate("/saves")}
        >
          <div className="rounded-full bg-slate-100 p-3">
            <Bookmark size={18} className="text-slate-700" />
          </div>
          <p className="text-sm font-semibold text-slate-800">Saqlangan ishlar</p>
          <p className="text-xs text-slate-500">{saves.list.isLoading ? "..." : `${savesCount} ta`}</p>
        </button>

        <button
          className="card tap-target flex flex-col items-center gap-2 p-4 text-center"
          onClick={() => navigate("/wallet")}
        >
          <div className="rounded-full bg-amber-50 p-3">
            <Wallet size={18} className={isPro ? "text-amber-500" : "text-slate-500"} />
          </div>
          <p className="text-sm font-semibold text-slate-800">Hamyon</p>
          <p className="text-xs text-slate-500">{wallet.isLoading ? "..." : `${fmt(balance)} so'm`}</p>
        </button>
      </section>

      {/* Referral invite */}
      <section className="card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-emerald-600" />
            <h3 className="text-sm font-semibold text-slate-800">Do'stlarni taklif qiling</h3>
          </div>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-700">
            +{fmt(wallet.data?.referral_reward ?? 2000)} so'm
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Har bir taklif qilgan do'stingiz uchun hisobingizga pul tushadi.
        </p>
        <div className="mt-3 flex gap-2">
          <button
            className="tap-target flex-1 rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white flex items-center justify-center gap-2"
            onClick={shareRef}
          >
            <Share2 size={15} />
            Ulashish
          </button>
          <button
            className="tap-target rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-700"
            onClick={() => navigate("/referral")}
          >
            Statistika
          </button>
        </div>
      </section>

      {/* Referral gate status (if enabled) */}
      {referralStats.data?.enabled && (
        <section className="card p-4">
          <h3 className="text-sm font-semibold text-slate-800">Kirish sharti</h3>
          <div className="mt-2 flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
            <span className="text-slate-500">Referallar</span>
            <span className={`font-semibold ${referralStats.data.unlocked ? "text-emerald-600" : "text-amber-600"}`}>
              {referralStats.data.current}/{referralStats.data.required}
              {referralStats.data.unlocked ? " ✓" : ""}
            </span>
          </div>
        </section>
      )}
    </div>
  );
}

