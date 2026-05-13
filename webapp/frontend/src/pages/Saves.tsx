import { Trash2 } from "lucide-react";

import { useSaves } from "../hooks/useSaves";

export default function Saves() {
  const { list, remove } = useSaves(1, 20);

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
