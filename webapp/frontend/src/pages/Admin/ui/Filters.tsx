/* eslint-disable react-refresh/only-export-components -- the kit ships helpers next to their component. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useHistorySheet, type HistorySheet } from "../hooks/useHistorySheet";
import Button from "./Button";
import { Chip } from "./Chip";
import { SheetFrame } from "./Sheet";

export type FilterOptionDef = {
  value: string;
  labelKey?: TranslationKey;
  label?: string;
};

export type FilterDef = {
  /** URL parameter name. `date-range` uses `<key>_from` / `<key>_to`. */
  key: string;
  labelKey: TranslationKey;
  type: "select" | "toggle" | "date-range" | "text";
  options?: FilterOptionDef[];
  placeholderKey?: TranslationKey;
};

export type FilterValues = Record<string, string>;

export type AdminFilterState = {
  /** Every filter parameter currently in the URL. */
  values: FilterValues;
  set: (key: string, value: string) => void;
  /** One history entry for a whole sheet of changes. */
  setMany: (next: FilterValues) => void;
  clear: () => void;
  activeCount: number;
  /** The history entry behind the "Filtrlar (n)" sheet. */
  sheet: HistorySheet;
};

/** The URL parameters one definition owns. */
export function filterParamKeys(def: FilterDef): string[] {
  return def.type === "date-range" ? [`${def.key}_from`, `${def.key}_to`] : [def.key];
}

/**
 * Filter state bound to the URL: one source of truth, shareable, and "back"
 * undoes the last change (spec §2).
 *
 *   const filters = useAdminFilters(USER_FILTERS);
 *   <FilterChips defs={USER_FILTERS} state={filters} />
 *   useCursorQuery(["admin","users",filters.values], …)
 */
export function useAdminFilters(defs: FilterDef[], sheetName = "filters"): AdminFilterState {
  const location = useLocation();
  const navigate = useNavigate();
  const sheet = useHistorySheet(sheetName);

  const keys = useMemo(() => defs.flatMap(filterParamKeys), [defs]);
  const search = location.search;

  const values = useMemo(() => {
    const params = new URLSearchParams(search);
    const out: FilterValues = {};
    for (const key of keys) {
      const value = params.get(key);
      if (value) out[key] = value;
    }
    return out;
  }, [keys, search]);

  const write = useCallback(
    (mutate: (params: URLSearchParams) => void, replace = false) => {
      const params = new URLSearchParams(search);
      mutate(params);
      const query = params.toString();
      navigate(`${location.pathname}${query ? `?${query}` : ""}`, {
        replace,
        state: location.state,
      });
    },
    [location.pathname, location.state, navigate, search],
  );

  const set = useCallback(
    (key: string, value: string) => {
      write((params) => {
        if (value) params.set(key, value);
        else params.delete(key);
      });
    },
    [write],
  );

  const setMany = useCallback(
    (next: FilterValues) => {
      write((params) => {
        for (const key of keys) {
          const value = next[key];
          if (value) params.set(key, value);
          else params.delete(key);
        }
      });
    },
    [keys, write],
  );

  const clear = useCallback(() => {
    write((params) => {
      for (const key of keys) params.delete(key);
    });
  }, [keys, write]);

  const activeCount = defs.filter((def) =>
    filterParamKeys(def).some((key) => Boolean(values[key])),
  ).length;

  return { values, set, setMany, clear, activeCount, sheet };
}

const INPUT =
  "h-9 w-full rounded-xl border border-border bg-surface px-2.5 text-[13px] text-text placeholder:text-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

function optionLabel(
  def: FilterDef,
  value: string,
  t: ReturnType<typeof useT>,
): string {
  const option = def.options?.find((entry) => entry.value === value);
  if (!option) return value;
  return option.labelKey ? t(option.labelKey) : (option.label ?? value);
}

export type FilterSheetProps = {
  defs: FilterDef[];
  state: AdminFilterState;
};

/** The grouped filter editor behind the "Filtrlar (n)" button. */
export function FilterSheet({ defs, state }: FilterSheetProps) {
  const t = useT();
  const [draft, setDraft] = useState<FilterValues>(state.values);
  const open = state.sheet.open;

  useEffect(() => {
    if (open) setDraft(state.values);
    // Re-seeding on every `values` change would fight the user's typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const put = (key: string, value: string) => setDraft((prev) => ({ ...prev, [key]: value }));

  return (
    <SheetFrame
      open={open}
      onClose={state.sheet.close}
      titleKey="admin.filter.title"
      footer={
        <div className="flex gap-2">
          <Button
            size="md"
            variant="secondary"
            labelKey="admin.filter.clear"
            onClick={() => {
              setDraft({});
              state.sheet.close();
              state.clear();
            }}
          />
          <Button
            size="md"
            full
            variant="primary"
            labelKey="admin.filter.apply"
            onClick={() => {
              state.sheet.close();
              state.setMany(draft);
            }}
          />
        </div>
      }
    >
      <div className="space-y-2.5">
        {defs.map((def) => {
          const label = t(def.labelKey);
          if (def.type === "toggle") {
            const on = draft[def.key] === "1";
            return (
              <button
                key={def.key}
                type="button"
                role="switch"
                aria-checked={on}
                onClick={() => put(def.key, on ? "" : "1")}
                className={`flex min-h-[40px] w-full items-center justify-between rounded-xl border px-3 text-[13px] font-medium ${
                  on ? "border-primary bg-primary/10 text-primary" : "border-border bg-surface text-text"
                }`}
              >
                {label}
                <span className="text-[11px] text-muted">
                  {on ? t("admin.filter.on") : t("admin.filter.all")}
                </span>
              </button>
            );
          }

          if (def.type === "date-range") {
            return (
              <div key={def.key}>
                <p className="mb-1 text-[11px] font-semibold text-muted">{label}</p>
                <div className="flex items-center gap-1.5">
                  <input
                    type="date"
                    value={draft[`${def.key}_from`] ?? ""}
                    max={draft[`${def.key}_to`] || undefined}
                    onChange={(event) => put(`${def.key}_from`, event.target.value)}
                    aria-label={t("admin.filter.from")}
                    className={INPUT}
                  />
                  <span aria-hidden="true" className="text-[11px] text-muted">
                    —
                  </span>
                  <input
                    type="date"
                    value={draft[`${def.key}_to`] ?? ""}
                    min={draft[`${def.key}_from`] || undefined}
                    onChange={(event) => put(`${def.key}_to`, event.target.value)}
                    aria-label={t("admin.filter.to")}
                    className={INPUT}
                  />
                </div>
              </div>
            );
          }

          if (def.type === "select") {
            return (
              <label key={def.key} className="block">
                <span className="mb-1 block text-[11px] font-semibold text-muted">{label}</span>
                <select
                  value={draft[def.key] ?? ""}
                  onChange={(event) => put(def.key, event.target.value)}
                  className={INPUT}
                >
                  <option value="">{t("admin.filter.all")}</option>
                  {(def.options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.labelKey ? t(option.labelKey) : (option.label ?? option.value)}
                    </option>
                  ))}
                </select>
              </label>
            );
          }

          return (
            <label key={def.key} className="block">
              <span className="mb-1 block text-[11px] font-semibold text-muted">{label}</span>
              <input
                type="text"
                value={draft[def.key] ?? ""}
                onChange={(event) => put(def.key, event.target.value)}
                placeholder={def.placeholderKey ? t(def.placeholderKey) : undefined}
                className={INPUT}
              />
            </label>
          );
        })}
      </div>
    </SheetFrame>
  );
}

export type FilterChipsProps = {
  defs: FilterDef[];
  state: AdminFilterState;
  className?: string;
};

/**
 * One 44px row: the active filters as removable chips plus the sheet trigger
 * (spec §4b — Users went from ~240px of controls to this).
 */
export function FilterChips({ defs, state, className = "" }: FilterChipsProps) {
  const t = useT();

  const chips = defs.flatMap((def) =>
    filterParamKeys(def)
      .filter((key) => Boolean(state.values[key]))
      .map((key) => {
        const raw = state.values[key];
        const value =
          def.type === "select"
            ? optionLabel(def, raw, t)
            : def.type === "toggle"
              ? t("admin.filter.on")
              : raw;
        return { key, label: `${t(def.labelKey)}: ${value}` };
      }),
  );

  return (
    <div className={`flex min-h-[32px] flex-wrap items-center gap-1.5 ${className}`}>
      <Button
        size="sm"
        variant="secondary"
        icon={SlidersHorizontal}
        onClick={() => state.sheet.openSheet()}
      >
        {state.activeCount > 0
          ? t("admin.filter.openCount", { count: state.activeCount })
          : t("admin.filter.open")}
      </Button>

      {chips.map((chip) => (
        <Chip
          key={chip.key}
          label={chip.label}
          tone="primary"
          removable
          onRemove={() => state.set(chip.key, "")}
        />
      ))}

      <FilterSheet defs={defs} state={state} />
    </div>
  );
}

export default FilterChips;
