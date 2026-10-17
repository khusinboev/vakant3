import { useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";

import BottomSheet from "../ui/BottomSheet";
import { useDistricts, useRegions, regionName } from "../../hooks/useStaticList";
import { useT } from "../../i18n/useT";
import type { TranslationKey } from "../../i18n";

export type SearchFilterValue = {
  query: string;
  specs: string;
  region_soato: string;
  district_soato: string;
  money: number;
  sort_key: string;
  sort_type: string;
};

type Props = {
  value: SearchFilterValue;
  onChange: (next: SearchFilterValue) => void;
};

const SECTOR_CHIPS: Array<{ id: string; labelKey: TranslationKey }> = [
  { id: "", labelKey: "filters.sector.all" },
  { id: "spec:21", labelKey: "filters.sector.industry" },
  { id: "spec:48", labelKey: "filters.sector.services" },
  { id: "spec:42", labelKey: "filters.sector.education" },
  { id: "spec:47", labelKey: "filters.sector.health" },
  { id: "spec:41", labelKey: "filters.sector.construction" },
  { id: "spec:12", labelKey: "filters.sector.it" },
  { id: "spec:64", labelKey: "filters.sector.trade" },
];

const SORT_CHIPS: Array<{ labelKey: TranslationKey; sort_key: string; sort_type: string }> = [
  { labelKey: "filters.sortNew", sort_key: "published_at", sort_type: "desc" },
  { labelKey: "filters.sortSalary", sort_key: "salary", sort_type: "desc" },
  { labelKey: "filters.sortOld", sort_key: "published_at", sort_type: "asc" },
];

const MONEY_TIERS = [0, 2_000_000, 3_000_000, 4_000_000, 5_000_000];

const selectCls =
  "tap-target rounded-2xl border border-border bg-surface px-3 text-sm text-text";

export default function SearchFilters({ value, onChange }: Props) {
  const t = useT();
  const [filtersOpen, setFiltersOpen] = useState(false);

  const regions = useRegions();
  const districts = useDistricts(value.region_soato);

  const activeFiltersCount = [
    Boolean(value.region_soato),
    Boolean(value.district_soato),
    value.money > 0,
    Boolean(value.sort_key),
    Boolean(value.sort_type),
  ].filter(Boolean).length;

  const moneyLabel = (tier: number) =>
    tier === 0 ? t("filters.salary") : t("filters.salaryFrom", { n: tier / 1_000_000 });

  return (
    <section className="card p-3">
      <div className="flex items-center gap-2">
        <label className="relative flex-1">
          <Search size={17} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={value.query}
            onChange={(e) => onChange({ ...value, query: e.target.value })}
            placeholder={t("filters.searchPlaceholder")}
            aria-label={t("filters.searchPlaceholder")}
            className="tap-target w-full rounded-2xl border border-border bg-surfaceAlt py-2 pl-10 pr-3 text-sm text-text outline-none transition placeholder:text-muted focus:border-primary focus:bg-surface"
          />
        </label>

        <button
          type="button"
          className="tap-target relative inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-surfaceAlt text-text"
          onClick={() => setFiltersOpen(true)}
          aria-label={t("filters.open")}
        >
          <SlidersHorizontal size={18} />
          {activeFiltersCount > 0 ? (
            <span className="absolute right-1.5 top-1.5 h-2.5 w-2.5 rounded-full bg-danger" />
          ) : null}
        </button>
      </div>

      <div className="mt-3">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted">
          {t("filters.sectors")}
        </p>
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
          {SECTOR_CHIPS.map((spec) => {
            const active = value.specs === spec.id;
            return (
              <button
                type="button"
                key={spec.id || "all"}
                className={`tap-target shrink-0 rounded-full border px-3 text-sm transition ${active ? "border-primary bg-primary text-primaryFg" : "border-border bg-surface text-muted"}`}
                onClick={() => onChange({ ...value, specs: spec.id })}
              >
                {t(spec.labelKey)}
              </button>
            );
          })}
        </div>
      </div>

      <BottomSheet
        open={filtersOpen}
        onClose={() => setFiltersOpen(false)}
        title={t("filters.allFilters")}
      >
        <div className="space-y-3">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted">
              {t("filters.sort")}
            </p>
            <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
              {SORT_CHIPS.map((chip) => {
                const active = value.sort_key === chip.sort_key && value.sort_type === chip.sort_type;
                return (
                  <button
                    type="button"
                    key={chip.labelKey}
                    className={`tap-target shrink-0 rounded-full border px-3 text-sm transition ${active ? "border-primary bg-primary text-primaryFg" : "border-border bg-surface text-muted"}`}
                    onClick={() => onChange({ ...value, sort_key: chip.sort_key, sort_type: chip.sort_type })}
                  >
                    {t(chip.labelKey)}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-3">
            <select
              className={selectCls}
              aria-label={t("filters.allRegions")}
              value={value.region_soato}
              onChange={(e) => onChange({ ...value, region_soato: e.target.value, district_soato: "" })}
            >
              <option value="">{t("filters.allRegions")}</option>
              {(regions.data ?? []).map((region) => (
                <option key={region.soato} value={region.soato}>
                  {regionName(region)}
                </option>
              ))}
            </select>

            <select
              className={selectCls}
              aria-label={t("filters.allDistricts")}
              value={value.district_soato}
              onChange={(e) => onChange({ ...value, district_soato: e.target.value })}
            >
              <option value="">{t("filters.allDistricts")}</option>
              {(districts.data ?? []).map((district) => (
                <option key={district.soato} value={district.soato}>
                  {district.name_uz}
                </option>
              ))}
            </select>

            <select
              className={selectCls}
              aria-label={t("filters.salary")}
              value={value.money}
              onChange={(e) => onChange({ ...value, money: Number(e.target.value) })}
            >
              {MONEY_TIERS.map((tier) => (
                <option key={tier} value={tier}>
                  {moneyLabel(tier)}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            className="tap-target w-full rounded-2xl bg-primary py-2.5 text-sm font-semibold text-primaryFg"
            onClick={() => setFiltersOpen(false)}
          >
            {t("common.apply")}
          </button>

          <button
            type="button"
            className="tap-target w-full rounded-2xl border border-border py-2.5 text-sm font-medium text-muted"
            onClick={() =>
              onChange({
                query: value.query,
                specs: value.specs,
                region_soato: "",
                district_soato: "",
                money: 0,
                sort_key: "",
                sort_type: "",
              })
            }
          >
            {t("filters.clear")}
          </button>
        </div>
      </BottomSheet>
    </section>
  );
}
