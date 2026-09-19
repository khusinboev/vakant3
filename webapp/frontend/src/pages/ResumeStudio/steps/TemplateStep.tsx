import { AlertCircle, ChevronRight, Loader2, Send } from "lucide-react";

import { useT } from "../../../i18n/useT";
import ResumePreview from "../ResumePreview";
import TemplatePreview from "../TemplatePreview";
import type { ResumeDoc, ResumeTemplateItem } from "../types";
import PhotoUpload from "./PhotoUpload";
import TemplateSheet from "./TemplateSheet";
import type { StepProps } from "./common";

const BADGE_CLS = "rounded-full px-1.5 py-[2px] text-[8px] font-bold";

export type TemplateStepProps = StepProps & {
  templates: ResumeTemplateItem[];
  activeTemplate?: ResumeTemplateItem;
  isPro: boolean;
  sheetOpen: boolean;
  onSheetOpenChange: (open: boolean) => void;
  onPremiumBlocked: () => void;
  /** Debounced copy of the document, so typing does not re-render the preview. */
  previewDoc: ResumeDoc;
  onSend: () => void;
  sending: boolean;
  busy: boolean;
};

export default function TemplateStep({
  draft,
  errors,
  templates,
  activeTemplate,
  isPro,
  sheetOpen,
  onSheetOpenChange,
  onPremiumBlocked,
  previewDoc,
  onSend,
  sending,
  busy,
}: TemplateStepProps) {
  const t = useT();
  const { profile, selectedTemplate, accentColor, setSelectedTemplate, setAccentColor, patchProfile } = draft;

  const thumbColor = activeTemplate?.supports_color
    ? accentColor
    : activeTemplate?.palette[0] || "#111827";
  const previewTemplateName =
    templates.find((item) => item.id === previewDoc.selectedTemplate)?.title ?? "";

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-muted">
          {t("resume.tpl.section")}
        </p>
        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-2xl border-2 border-border bg-surface p-3 text-left transition-all hover:border-primary/40 hover:shadow-sm"
          onClick={() => onSheetOpenChange(true)}
        >
          <div className="h-[54px] w-[58px] shrink-0 overflow-hidden rounded-lg border border-border bg-surfaceAlt">
            <div className="pointer-events-none w-[108px] origin-top-left" style={{ transform: "scale(0.537)" }}>
              <TemplatePreview id={selectedTemplate} color={thumbColor} />
            </div>
          </div>

          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-text">{activeTemplate?.title}</p>
            <p className="mt-0.5 line-clamp-1 text-xs leading-snug text-muted">
              {activeTemplate?.description}
            </p>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {activeTemplate?.supports_photo && (
                <span className={`${BADGE_CLS} bg-warning/20 text-warning`}>
                  📷 {t("resume.tpl.badgePhoto")}
                </span>
              )}
              {activeTemplate?.supports_sidebar && (
                <span className={`${BADGE_CLS} bg-primary/15 text-primary`}>
                  {t("resume.tpl.badgeSidebar")}
                </span>
              )}
              {activeTemplate && !activeTemplate.supports_color && (
                <span className={`${BADGE_CLS} bg-surfaceAlt text-muted`}>{t("resume.tpl.badgeMono")}</span>
              )}
              {activeTemplate?.supports_color && (
                <span className={`${BADGE_CLS} text-white`} style={{ backgroundColor: accentColor }}>
                  ● {t("resume.tpl.badgeColor")}
                </span>
              )}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-0.5">
            <span className="text-[11px] font-semibold text-primary">{t("resume.tpl.change")}</span>
            <ChevronRight size={13} className="text-primary/70" />
          </div>
        </button>
      </div>

      <TemplateSheet
        open={sheetOpen}
        onClose={() => onSheetOpenChange(false)}
        templates={templates}
        selectedId={selectedTemplate}
        accentColor={accentColor}
        activeTemplate={activeTemplate}
        isPro={isPro}
        onSelect={setSelectedTemplate}
        onAccentChange={setAccentColor}
        onLockedPick={onPremiumBlocked}
      />

      {activeTemplate?.supports_photo && (
        <PhotoUpload value={profile.photo_url} onChange={(photo_url) => patchProfile({ photo_url })} />
      )}

      {errors.template && (
        <p className="flex items-center gap-1 text-xs text-danger">
          <AlertCircle size={11} /> {errors.template}
        </p>
      )}

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
          {t("resume.previewTitle")}
        </p>
        <ResumePreview
          profile={previewDoc.profile}
          accentColor={previewDoc.accentColor}
          templateName={previewTemplateName}
        />
      </div>

      <div className="rounded-2xl border border-border bg-surface p-4">
        <p className="mb-2.5 text-xs font-bold text-text">{t("resume.send.title")}</p>
        <button
          type="button"
          className="tap-target flex w-full items-center justify-center gap-2 rounded-2xl bg-success py-4 text-sm font-bold text-white shadow-lg disabled:opacity-60"
          disabled={busy}
          onClick={onSend}
        >
          {sending ? (
            <>
              <Loader2 size={16} className="animate-spin" /> {t("resume.send.sending")}
            </>
          ) : (
            <>
              <Send size={16} /> {t("resume.send.button")}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
