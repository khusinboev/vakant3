import { useState } from "react";
import { Trash2 } from "lucide-react";

import LoginPrompt from "../components/LoginPrompt";
import { useSaves } from "../hooks/useSaves";
import { useAuthStore } from "../store/auth";

export default function Saves() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [showPrompt, setShowPrompt] = useState(false);
  const { list, remove } = useSaves(1, 20, isAuthenticated);

  if (!isAuthenticated) {
    return (
      <>
        <div className="card flex flex-col items-center gap-4 p-8 text-center">
          <p className="text-base font-semibold text-slate-700">Saqlangan ishlar</p>
          <p className="text-sm text-slate-500">Vakansiyalarni saqlash uchun botda hisobingiz bo'lishi kerak.</p>
          <button
            className="tap-target rounded-2xl bg-brand-500 px-5 py-3 text-sm font-semibold text-white"
            onClick={() => setShowPrompt(true)}
          >
            Kirish
          </button>
        </div>
        {showPrompt && <LoginPrompt onClose={() => setShowPrompt(false)} />}
      </>
    );
  }

  if (list.isLoading) {
    return <div className="card p-4 text-sm">Yuklanmoqda...</div>;
  }

  if (list.isError) {
    return <div className="card p-4 text-sm text-red-600">Saqlangan ishlarni yuklab bo'lmadi.</div>;
  }

  if (!list.data?.items.length) {
    return <div className="card p-4 text-sm">Saqlangan ishlar yo'q. Ishlarni saqlash uchun ❤ tugmasini bosing</div>;
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {list.data.items.map((item) => (
        <article key={item.uid} className="card p-4">
          <p className="text-sm font-semibold">{String(item.data.title || "Vakansiya")}</p>
          <p className="mt-1 text-xs text-slate-500">{String(item.data.address || "")}</p>
          <button
            className="tap-target mt-3 inline-flex items-center gap-2 rounded-xl border border-red-300 px-3 text-sm text-red-600"
            onClick={() => remove.mutate(item.uid)}
          >
            <Trash2 size={16} /> O'chirish
          </button>
        </article>
      ))}
    </div>
  );
}
