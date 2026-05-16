type Props = {
  refLink: string;
  count: number;
  reward?: number;
};

export function shareRefLink(refLink: string) {
  const tg = window.Telegram?.WebApp;
  const shareText = "Bandlik.uz — Telegram orqali ish topishning eng qulay yo'li! Qo'shiling:";
  const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(refLink)}&text=${encodeURIComponent(shareText)}`;
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(shareUrl);
  } else {
    window.open(shareUrl, "_blank");
  }
}

export default function ReferralCard({ refLink, count, reward = 2000 }: Props) {
  function copy() {
    navigator.clipboard.writeText(refLink);
  }

  return (
    <section className="card overflow-hidden p-0">
      <div className="bg-gradient-to-br from-emerald-600 to-emerald-700 px-5 py-5 text-white">
        <p className="text-sm font-medium opacity-90">Har bir taklif uchun</p>
        <p className="mt-1 text-3xl font-bold tracking-tight">+{reward.toLocaleString("uz-UZ")} so'm</p>
        <p className="mt-1 text-xs opacity-75">Hisobingizga avtomatik tushadi</p>
      </div>
      <div className="p-4">
        <p className="text-xs text-slate-500 mb-2">Sizning havola</p>
        <div className="flex gap-2">
          <div className="flex-1 truncate rounded-xl bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-700">{refLink}</div>
          <button onClick={copy} className="tap-target shrink-0 rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700">
            Nusxa
          </button>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <p className="text-sm text-slate-600">Taklif qilinganlar: <strong>{count}</strong> ta</p>
          <button onClick={() => shareRefLink(refLink)} className="tap-target rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">
            Ulashish
          </button>
        </div>
      </div>
    </section>
  );
}

