type Props = {
  memberSince: string;
  savesCount: number;
  referralsCount: number;
  regionText: string;
};

export default function StatsGrid({ memberSince, savesCount, referralsCount, regionText }: Props) {
  const cards = [
    { title: "A'zo bo'lgan sana", value: memberSince },
    { title: "Saqlangan ishlar", value: String(savesCount) },
    { title: "Taklif qilinganlar", value: String(referralsCount) },
    { title: "Joriy hudud", value: regionText || "Tanlanmagan" }
  ];

  return (
    <section className="grid gap-3 sm:grid-cols-2">
      {cards.map((card) => (
        <article key={card.title} className="card p-4">
          <p className="text-xs text-slate-500">{card.title}</p>
          <p className="mt-1 text-lg font-semibold">{card.value}</p>
        </article>
      ))}
    </section>
  );
}
