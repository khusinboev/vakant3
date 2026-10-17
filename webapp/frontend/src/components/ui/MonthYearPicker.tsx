import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import BottomSheet from "./BottomSheet";
import { CURRENT_YEAR, YEARS, formatMonthYear, isPresentValue, monthNames, presentValueFor } from "./monthYear";
import { useLocale } from "../../i18n/useLocale";
import { useT } from "../../i18n/useT";

export type MonthYearPickerProps = {
  /** `"MM/YYYY"`, `"YYYY"`, a present token, or "". */
  value: string;
  onChange: (value: string) => void;
  /** Offer an "ongoing" choice (end dates only). */
  withCurrent?: boolean;
};

/**
 * Month + year picker in a bottom sheet — a mobile-friendly stand-in for
 * `<input type="month">`, which Telegram's in-app webview renders poorly.
 * Its labels come from the `resume.date.*` translation keys.
 */
export default function MonthYearPicker({ value, onChange, withCurrent = false }: MonthYearPickerProps) {
  const t = useT();
  const { lang, locale } = useLocale();
  const [open, setOpen] = useState(false);
  const [yearText, setYearText] = useState("");
  const yearListRef = useRef<HTMLDivElement>(null);

  const months = useMemo(() => monthNames(locale), [locale]);
  const presentLabel = t("resume.date.presentShort");
  const isCurrent = isPresentValue(value);
  // "MM/YYYY" -> month + year; a bare "YYYY" is a year, never a month.
  const parts = isCurrent ? [] : (value || "").trim().split("/");
  const selMonth = parts.length === 2 ? parts[0] : "";
  const year = parts.length === 2 ? parts[1] : (parts[0] ?? "");
  const label = formatMonthYear(value, locale, presentLabel);

  // Scroll the selected year into view once the sheet has painted.
  useEffect(() => {
    if (!open) return;
    const id = setTimeout(() => {
      const node = yearListRef.current?.querySelector<HTMLElement>('[data-sel="true"]');
      node?.scrollIntoView({ block: "center" });
    }, 60);
    return () => clearTimeout(id);
  }, [open]);

  const handleOpen = () => {
    setYearText(year);
    setOpen(true);
  };

  const pickYear = (picked: string) => {
    setYearText(picked);
    onChange(selMonth ? `${selMonth}/${picked}` : picked);
    if (selMonth) setOpen(false);
  };

  const handleYearTyped = (raw: string) => {
    const clean = raw.replace(/\D/g, "").slice(0, 4);
    setYearText(clean);
    if (clean.length !== 4) return;
    const parsed = Number(clean);
    if (parsed >= 1950 && parsed <= CURRENT_YEAR + 5) {
      onChange(selMonth ? `${selMonth}/${clean}` : clean);
    }
  };

  const optionCls = (selected: boolean) =>
    `mb-1 w-full rounded-xl px-3 py-2.5 text-left text-sm font-medium transition-colors ${
      selected ? "bg-primary text-primaryFg" : "bg-surfaceAlt text-text active:opacity-80"
    }`;

  return (
    <>
      <button
        type="button"
        className={`flex w-full items-center justify-between rounded-xl border bg-surface px-3 py-2.5 text-left text-sm transition-all focus:outline-none ${
          label ? "border-border text-text" : "border-border text-muted"
        }`}
        onClick={handleOpen}
      >
        <span className="truncate">{label || t("resume.date.placeholder")}</span>
        <ChevronDown size={14} className="ml-1 shrink-0 text-muted" />
      </button>

      <BottomSheet open={open} onClose={() => setOpen(false)} title={t("resume.date.sheetTitle")}>
        {withCurrent && (
          <button
            type="button"
            className={`mb-3 w-full rounded-xl py-2.5 text-sm font-bold transition-colors ${
              isCurrent ? "bg-success text-white" : "bg-surfaceAlt text-muted"
            }`}
            onClick={() => {
              onChange(presentValueFor(lang));
              setOpen(false);
            }}
          >
            {isCurrent ? `✓ ${t("resume.date.present")}` : t("resume.date.present")}
          </button>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col">
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-muted">
              {t("resume.date.month")}
            </p>
            <div className="overflow-y-auto" style={{ maxHeight: "44vh" }}>
              {months.map((name, index) => {
                const val = String(index + 1).padStart(2, "0");
                const selected = !isCurrent && selMonth === val;
                return (
                  <button
                    type="button"
                    key={name}
                    className={optionCls(selected)}
                    onClick={() => {
                      onChange(year ? `${val}/${year}` : val);
                      if (year) setOpen(false);
                    }}
                  >
                    {name}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col">
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-muted">
              {t("resume.date.year")}
            </p>
            <input
              type="text"
              inputMode="numeric"
              maxLength={4}
              aria-label={t("resume.date.year")}
              placeholder={String(CURRENT_YEAR)}
              value={yearText}
              onChange={(event) => handleYearTyped(event.target.value)}
              className="mb-2 w-full rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-muted/70 focus:border-primary focus:outline-none"
            />
            <div ref={yearListRef} className="overflow-y-auto" style={{ maxHeight: "calc(44vh - 54px)" }}>
              {YEARS.map((item) => {
                const selected = !isCurrent && year === item;
                return (
                  <button
                    type="button"
                    key={item}
                    data-sel={selected ? "true" : undefined}
                    className={optionCls(selected)}
                    onClick={() => pickYear(item)}
                  >
                    {item}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {(selMonth || year || isCurrent) && (
          <button
            type="button"
            className="mt-3 w-full rounded-xl border border-border py-2.5 text-xs font-semibold text-muted"
            onClick={() => {
              onChange("");
              setYearText("");
              setOpen(false);
            }}
          >
            {t("resume.date.clear")}
          </button>
        )}
      </BottomSheet>
    </>
  );
}
