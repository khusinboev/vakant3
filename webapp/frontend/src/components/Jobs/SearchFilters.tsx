import { useEffect, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";

import client from "../../api/client";

type Region = { soato: string; name_uz: string };

type Props = {
  value: {
    query: string;
    specs: string;
    region_soato: string;
    district_soato: string;
    money: number;
    sort_key: string;
    sort_type: string;
  };
  onChange: (next: {
    query: string;
    specs: string;
    region_soato: string;
    district_soato: string;
    money: number;
    sort_key: string;
    sort_type: string;
  }) => void;
};

const SECTOR_CHIPS = [
  { id: "", label: "Barchasi" },
  { id: "spec:21", label: "Sanoat" },
  { id: "spec:48", label: "Xizmatlar" },
  { id: "spec:42", label: "Ta'lim" },
  { id: "spec:47", label: "Sog'liq" },
  { id: "spec:41", label: "Qurilish" },
  { id: "spec:12", label: "IT" },
  { id: "spec:64", label: "Savdo" }
];

const SORT_CHIPS = [
  { label: "Yangi", sort_key: "published_at", sort_type: "desc" },
  { label: "Yuqori maosh", sort_key: "salary", sort_type: "desc" },
  { label: "Eski", sort_key: "published_at", sort_type: "asc" }
];

const MONEY = [
  { value: 0, label: "Maosh" },
  { value: 2000000, label: "2 mln +" },
  { value: 3000000, label: "3 mln +" },
  { value: 4000000, label: "4 mln +" },
  { value: 5000000, label: "5 mln +" }
];

export default function SearchFilters({ value, onChange }: Props) {
  const [regions, setRegions] = useState<Region[]>([]);
  const [districts, setDistricts] = useState<Region[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    client.get<Region[]>("/filters/regions").then((res) => setRegions(res.data)).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!value.region_soato) {
      setDistricts([]);
      return;
    }
    client
      .get<Region[]>("/filters/districts", { params: { region_soato: value.region_soato } })
      .then((res) => setDistricts(res.data))
      .catch(() => setDistricts([]));
  }, [value.region_soato]);

  const activeFiltersCount = [
    Boolean(value.region_soato),
    Boolean(value.district_soato),
    value.money > 0,
    Boolean(value.sort_key),
    Boolean(value.sort_type)
  ].filter(Boolean).length;

  return (
    <section className="card p-3">
      <div className="flex items-center gap-2">
        <label className="relative flex-1">
          <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={value.query}
            onChange={(e) => onChange({ ...value, query: e.target.value })}
            placeholder="Kasb, lavozim nomi"
            className="tap-target w-full rounded-2xl border border-slate-300 bg-slate-50 py-2 pl-10 pr-3 text-sm outline-none transition focus:border-brand-400 focus:bg-white"
          />
        </label>

        <button
          className="relative tap-target inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-300 bg-slate-50 text-slate-700"
          onClick={() => setFiltersOpen(true)}
          aria-label="Filtrlarni ochish"
        >
          <SlidersHorizontal size={18} />
          {activeFiltersCount > 0 ? <span className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full bg-red-500" /> : null}
        </button>
      </div>

      <div className="mt-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Sohalar</p>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {SECTOR_CHIPS.map((spec) => {
            const active = value.specs === spec.id;
            return (
              <button
                key={spec.id || "all"}
                className={`tap-target shrink-0 rounded-full border px-3 text-sm transition ${active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-600"}`}
                onClick={() => onChange({ ...value, specs: spec.id })}
              >
                {spec.label}
              </button>
            );
          })}
        </div>
      </div>

      {filtersOpen ? (
        <div className="fixed inset-0 z-40 bg-slate-950/35" onClick={() => setFiltersOpen(false)}>
          <div
            className="absolute bottom-0 left-0 right-0 max-h-[85vh] overflow-y-auto rounded-t-3xl bg-white p-4 pb-[calc(1rem+var(--tg-content-safe-area-bottom))] pl-[calc(1rem+var(--tg-content-safe-area-left))] pr-[calc(1rem+var(--tg-content-safe-area-right))] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-900">Barcha filterlar</p>
              <button className="tap-target rounded-full border border-slate-300 p-2 text-slate-600" onClick={() => setFiltersOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Saralash</p>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {SORT_CHIPS.map((chip) => {
                    const active = value.sort_key === chip.sort_key && value.sort_type === chip.sort_type;
                    return (
                      <button
                        key={chip.label}
                        className={`tap-target shrink-0 rounded-full border px-3 text-sm transition ${active ? "border-brand-500 bg-brand-500 text-white" : "border-slate-300 bg-white text-slate-600"}`}
                        onClick={() => onChange({ ...value, sort_key: chip.sort_key, sort_type: chip.sort_type })}
                      >
                        {chip.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid gap-3">
            <select
              className="tap-target rounded-2xl border border-slate-300 bg-white px-3 text-sm"
              value={value.region_soato}
              onChange={(e) => onChange({ ...value, region_soato: e.target.value, district_soato: "" })}
            >
              <option value="">Barcha viloyatlar</option>
              {regions.map((region) => (
                <option key={region.soato} value={region.soato}>
                  {region.name_uz}
                </option>
              ))}
            </select>

            <select
              className="tap-target rounded-2xl border border-slate-300 bg-white px-3 text-sm"
              value={value.district_soato}
              onChange={(e) => onChange({ ...value, district_soato: e.target.value })}
            >
              <option value="">Barcha tumanlar</option>
              {districts.map((district) => (
                <option key={district.soato} value={district.soato}>
                  {district.name_uz}
                </option>
              ))}
            </select>

            <select
              className="tap-target rounded-2xl border border-slate-300 bg-white px-3 text-sm"
              value={value.money}
              onChange={(e) => onChange({ ...value, money: Number(e.target.value) })}
            >
              {MONEY.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
              </div>

              <button
                className="tap-target w-full rounded-2xl bg-slate-900 py-2.5 text-sm font-semibold text-white"
                onClick={() => setFiltersOpen(false)}
              >
                Qo‘llash
              </button>

              <button
                className="tap-target w-full rounded-2xl border border-slate-300 py-2.5 text-sm font-medium text-slate-600"
                onClick={() =>
                  onChange({
                    query: value.query,
                    specs: value.specs,
                    region_soato: "",
                    district_soato: "",
                    money: 0,
                    sort_key: "",
                    sort_type: ""
                  })
                }
              >
                Qo‘shimcha filterlarni tozalash
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
