import { Check } from "lucide-react";

import BottomSheet from "../../../components/ui/BottomSheet";
import { useT } from "../../../i18n/useT";
import { DARK_TEMPLATE_IDS } from "../data/templates";
import TemplatePreview from "../TemplatePreview";
import type { ResumeTemplateItem } from "../types";

const BADGE_CLS = "rounded-full px-1.5 py-[2px] text-[8px] font-bold";

export type TemplateSheetProps = {
  open: boolean;
  onClose: () => void;
  templates: ResumeTemplateItem[];
  selectedId: string;
  accentColor: string;
  activeTemplate?: ResumeTemplateItem;
  isPro: boolean;
  onSelect: (id: string) => void;
  onAccentChange: (color: string) => void;
  onLockedPick: () => void;
};

/** Template gallery + accent palette, in a bottom sheet. */
export default function TemplateSheet({
  open,
  onClose,
  templates,
  selectedId,
  accentColor,
  activeTemplate,
  isPro,
  onSelect,
  onAccentChange,
  onLockedPick,
}: TemplateSheetProps) {
  const t = useT();

  return (
    <BottomSheet open={open} onClose={onClose} title={t("resume.tpl.sheetTitle")}>
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          {templates.map((tpl) => {
            const selected = tpl.id === selectedId;
            const locked = Boolean(tpl.is_premium) && !isPro;
            const color = tpl.supports_color ? accentColor : tpl.palette[0] || "#111827";
            return (
              <button
                type="button"
                key={tpl.id}
                aria-label={t("resume.tpl.pick", { title: tpl.title })}
                aria-pressed={selected}
                className={`tap-target relative rounded-2xl border-2 p-2.5 text-left transition-all duration-150 ${
                  locked
                    ? "border-border bg-surfaceAlt opacity-80"
                    : selected
                      ? "border-primary bg-primary/10 shadow-lg"
                      : "border-border bg-surface hover:border-primary/40"
                }`}
                onClick={() => (locked ? onLockedPick() : onSelect(tpl.id))}
              >
                {/* The thumbnail draws a printed page, so its colours stay literal. */}
                <TemplatePreview id={tpl.id} color={locked ? "#94a3b8" : color} />

                {locked && (
                  <div className="pointer-events-none absolute inset-0 flex items-end justify-end rounded-2xl p-2">
                    <span className={`${BADGE_CLS} flex items-center gap-0.5 bg-warning text-white`}>
                      💎 {t("resume.tpl.badgePro")}
                    </span>
                  </div>
                )}

                <div className="mt-2 space-y-1">
                  <div className="flex items-start justify-between gap-1">
                    <p className="text-[11px] font-bold leading-tight text-text">{tpl.title}</p>
                    {selected && !locked && (
                      <span
                        className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
                        style={{ backgroundColor: accentColor }}
                      >
                        <Check size={9} className="text-white" />
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {tpl.supports_photo && (
                      <span className={`${BADGE_CLS} bg-warning/20 text-warning`}>
                        📷 {t("resume.tpl.badgePhoto")}
                      </span>
                    )}
                    {tpl.supports_sidebar && (
                      <span className={`${BADGE_CLS} bg-primary/15 text-primary`}>
                        {t("resume.tpl.badgeSidebar")}
                      </span>
                    )}
                    {!tpl.supports_color && (
                      <span className={`${BADGE_CLS} bg-surfaceAlt text-muted`}>
                        {t("resume.tpl.badgeMono")}
                      </span>
                    )}
                    {DARK_TEMPLATE_IDS.has(tpl.id) && (
                      <span className={`${BADGE_CLS} bg-text text-bg`}>{t("resume.tpl.badgeDark")}</span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {activeTemplate?.supports_color && (
          <div className="rounded-2xl border border-border bg-surfaceAlt p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="flex items-center gap-2 text-xs font-semibold text-text">
                <span
                  className="inline-block h-4 w-4 rounded-full border-2 border-surface shadow-sm"
                  style={{ backgroundColor: accentColor }}
                />
                {t("resume.tpl.accent")}
              </p>
              <span className="font-mono text-[10px] text-muted">{accentColor}</span>
            </div>
            <div className="flex flex-wrap gap-3">
              {(activeTemplate.palette || []).map((color) => (
                <button
                  type="button"
                  key={color}
                  title={color}
                  aria-label={color}
                  aria-pressed={accentColor === color}
                  className={`h-10 w-10 rounded-full transition-all duration-150 ${
                    accentColor === color
                      ? "scale-110 shadow-lg ring-[3px] ring-text ring-offset-2 ring-offset-surfaceAlt"
                      : "shadow ring-1 ring-border hover:scale-105"
                  }`}
                  style={{ backgroundColor: color }}
                  onClick={() => onAccentChange(color)}
                />
              ))}
            </div>
          </div>
        )}

        <button
          type="button"
          className="w-full rounded-2xl py-3.5 text-sm font-bold text-white shadow-lg"
          style={{ backgroundColor: accentColor || "#0f766e" }}
          onClick={onClose}
        >
          {t("resume.tpl.done")} ✓
        </button>
      </div>
    </BottomSheet>
  );
}
