import { Link } from "react-router-dom";

import { useSaves } from "../hooks/useSaves";

export default function Profile() {
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

  return (
    <div className="space-y-4">
      <section className="card p-4">
        <div className="flex items-center gap-3">
          <div className="h-14 w-14 overflow-hidden rounded-full border border-slate-200 bg-slate-100">
            {user.photo_url ? (
              <img src={user.photo_url} alt={fullName || "Avatar"} className="h-full w-full object-cover" />
            ) : null}
          </div>
          <div>
            <p className="text-base font-semibold text-slate-800">{fullName || "Telegram user"}</p>
            <p className="text-sm text-slate-500">{user.username ? `@${user.username}` : "@username yo'q"}</p>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Qisqa ma'lumot</h3>
        <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Telegram ID</span>
            <span className="font-medium text-slate-800">{user.id}</span>
          </div>
          <div className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2">
            <span className="text-slate-500">Saqlanganlar</span>
            <span className="font-medium text-slate-800">
              {saves.list.isLoading ? "Yuklanmoqda..." : `${savesCount} ta`}
            </span>
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h3 className="text-sm font-semibold text-slate-800">Tezkor amallar</h3>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <Link to="/saves" className="tap-target rounded-2xl bg-slate-900 px-4 py-3 text-center text-sm font-semibold text-white">
            Saqlangan ishlar
          </Link>
          <Link to="/referral" className="tap-target rounded-2xl border border-slate-200 px-4 py-3 text-center text-sm font-semibold text-slate-700">
            Referral sahifasi
          </Link>
        </div>
      </section>
    </div>
  );
}
