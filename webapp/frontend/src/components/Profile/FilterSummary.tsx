type Props = {
  specs: string | null;
  region: string | null;
  district: string | null;
  money: number | null;
};

export default function FilterSummary({ specs, region, district, money }: Props) {
  return (
    <section className="card p-4">
      <h3 className="font-semibold">Joriy filtrlar</h3>
      <div className="mt-2 space-y-1 text-sm text-slate-600">
        <p>Soha: {specs || "Tanlanmagan"}</p>
        <p>Hudud: {[region, district].filter(Boolean).join(" / ") || "Tanlanmagan"}</p>
        <p>Maosh: {money ? `${money.toLocaleString("ru-RU").replace(/,/g, " ")} so'm` : "Ahamiyatsiz"}</p>
      </div>
    </section>
  );
}
