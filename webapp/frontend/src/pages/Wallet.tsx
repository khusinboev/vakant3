import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Crown, Link, Wallet } from "lucide-react";
import { useNavigate } from "react-router-dom";

import client from "../api/client";
import { shareRefLink } from "../components/Referral/ReferralCard";
import { useAuthStore } from "../store/auth";

type WalletData = {
  balance: number;
  is_pro: boolean;
  pro_price: number;
  referral_reward: number;
};

function fmt(n: number) {
  return n.toLocaleString("uz-UZ");
}

export default function WalletPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const authUser = useAuthStore((s) => s.user);

  const wallet = useQuery({
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
    },
  });

  const w = wallet.data;

  const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
  const botUsername = (window as any).__BOT_USERNAME__ || "bandlikuzbot";
  const refUserId = tgUser?.id ?? authUser?.user_id;

  const refLink = refUserId
    ? `https://t.me/${botUsername}?start=ref_${refUserId}`
    : null;

  function copyRef() {
    if (refLink) navigator.clipboard.writeText(refLink);
  }

  if (wallet.isLoading) {
    return <div className="flex h-40 items-center justify-center text-sm text-slate-400">Yuklanmoqda...</div>;
  }

  if (!w) {
    return (
      <div className="card p-6 text-center text-sm text-slate-500">
        Hamyon ma'lumotlari topilmadi. Telegram orqali kiring.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Balance card */}
      <section className="card overflow-hidden p-0">
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 px-5 py-6 text-white">
          <div className="flex items-center gap-2 text-slate-300 text-sm">
            <Wallet size={16} />
            <span>Hamyon balansi</span>
          </div>
          <p className="mt-2 text-3xl font-bold tracking-tight">{fmt(w.balance)} so'm</p>
          {w.is_pro ? (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-amber-400 px-3 py-1 text-xs font-bold text-amber-900">
              <Crown size={13} />
              PRO tarif faol
            </div>
          ) : (
            <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-slate-600 px-3 py-1 text-xs font-medium text-slate-300">
              Boshlang'ich tarif
            </div>
          )}
        </div>
      </section>

      {/* Pro tarif section - REMOVED to focus on referral */}

      {/* Pro tariff quick info and activation */}
      {!w.is_pro && (
        <section className="card p-4">
          <h3 className="text-sm font-semibold text-slate-800">💎 Pro tarif</h3>
          <p className="mt-1 text-xs text-slate-600">
            Pro tarif bilan yuqori maoshli ishlar uchun kontakt raqamlar ochiladi.
          </p>
          <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Narxi</span>
              <span className="font-semibold text-slate-800">{fmt(w.pro_price)} so'm</span>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-slate-500">Balans</span>
              <span className={`font-semibold ${w.balance >= w.pro_price ? "text-emerald-600" : "text-red-500"}`}>
                {fmt(w.balance)} so'm
              </span>
            </div>
          </div>
          {w.balance >= w.pro_price ? (
            <button
              className="tap-target mt-3 w-full rounded-2xl bg-amber-500 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60"
              disabled={activatePro.isPending}
              onClick={() => activatePro.mutate()}
            >
              {activatePro.isPending ? "Faollashtirilmoqda..." : "Pro tarifni aktivlashtirish"}
            </button>
          ) : (
            <p className="mt-2 text-xs text-slate-500">
              Pro uchun yana {fmt(w.pro_price - w.balance)} so'm kerak.
            </p>
          )}
        </section>
      )}

      {/* How to get Pro - Referral focused */}
      {!w.is_pro && (
        <>
          {/* Referral earn - PRIMARY focus */}
          <section className="card p-4 bg-emerald-50 border-2 border-emerald-200">
            <h3 className="text-sm font-bold text-emerald-900 mb-3 flex items-center gap-2">
              🎁 Eng oson usul: Referral orqali
            </h3>
            <p className="text-sm text-emerald-800 mb-3">
              Do'stlaringizni taklif qiling. Har bir do'stingiz botga qo'shilganda hisobingizga <strong>{fmt(w.referral_reward)} so'm</strong> tushadi.
            </p>
            {refLink && (
              <div className="mb-3 flex gap-2">
                <button
                  className="tap-target flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-emerald-200 bg-white px-3 py-2 text-xs font-medium text-slate-700"
                  onClick={copyRef}
                  title={refLink}
                >
                  <Link size={14} className="shrink-0 text-emerald-700" />
                  <span className="min-w-0 flex-1 truncate font-mono text-[11px]">{refLink}</span>
                  <span className="shrink-0 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">Nusxa</span>
                </button>
                <button
                  className="tap-target shrink-0 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white flex items-center gap-1 hover:bg-emerald-700"
                  onClick={() => shareRefLink(refLink)}
                >
                  📤 Ulash
                </button>
              </div>
            )}
            <p className="text-xs text-emerald-700 mt-2 text-center">
              ✓ {fmt(w.pro_price)} so'm to'plamsa, Pro tarifni avtomatik yoqaman
            </p>
          </section>

          {/* Admin help - secondary option */}
          <section className="card p-4">
            <h3 className="text-sm font-semibold text-slate-800 mb-2">💳 Admin orqali pul qo'shish</h3>
            <p className="text-xs text-slate-600 mb-3">
              Agar darhol pro olishni xohlasangiz, admin orqali hisobingizga {fmt(w.pro_price)} so'm qo'shtirib berishini so'rashingiz mumkin.
            </p>
            <button
              className="tap-target w-full rounded-2xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white flex items-center justify-center gap-2 hover:bg-blue-700"
              onClick={() => {
                const adminUsername = "UnitedAgency";
                const msg = `Salom! Pro tarifga o'tish uchun hisobimga ${fmt(w.pro_price)} so'm qo'shib berish kerak.\n\nTelegram ID: ${tgUser?.id ?? "noma'lum"}\n\nRahmat!`;
                window.Telegram?.WebApp?.openTelegramLink?.(`https://t.me/${adminUsername}?text=${encodeURIComponent(msg)}`);
              }}
            >
              💬 Admin bilan bog'lanish
            </button>
          </section>
        </>
      )}

      {/* When pro is active */}
      {w.is_pro && (
        <>
          <section className="card p-4">
            <div className="flex items-center gap-3">
              <CheckCircle2 size={20} className="text-emerald-500 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-slate-800">Pro tarif faol</p>
                <p className="text-xs text-slate-500 mt-0.5">Barcha yuqori maoshli ish e'lonlari sizga ochiq.</p>
              </div>
            </div>
          </section>

          {/* Referral section for pro users */}
          <section className="card p-4">
            <h3 className="text-sm font-semibold text-slate-800 mb-2">🎁 Do'stlaringizni taklif qiling</h3>
            <p className="text-xs text-slate-600 mb-3">
              Har bir taklif qilgan do'stingiz uchun <strong>{fmt(w.referral_reward)} so'm</strong> qazanin.
            </p>
            {refLink && (
              <div className="mb-3 flex gap-2">
                <button
                  className="tap-target flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700"
                  onClick={copyRef}
                  title={refLink}
                >
                  <Link size={14} className="shrink-0 text-emerald-700" />
                  <span className="min-w-0 flex-1 truncate font-mono text-[11px]">{refLink}</span>
                  <span className="shrink-0 rounded-md bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">Nusxa</span>
                </button>
                <button
                  className="tap-target shrink-0 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white flex items-center gap-1"
                  onClick={() => shareRefLink(refLink)}
                >
                  📤 Ulash
                </button>
              </div>
            )}
          </section>
        </>
      )}

      {/* Referral statistics - always visible */}
      <section className="card p-4">
        <button
          className="tap-target w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-600 text-left hover:bg-slate-50"
          onClick={() => navigate("/referral")}
        >
          📊 Referral statistikasi →
        </button>
      </section>

    </div>
  );
}
