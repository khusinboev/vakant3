import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronLeft, ChevronRight, FileText, Loader2, Send } from "lucide-react";

import BottomNav from "../../components/Layout/BottomNav";
import { clearBackInterceptor, setBackInterceptor } from "../../hooks/useBackInterceptor";
import { useKeyboardOpen } from "../../hooks/useKeyboardOpen";
import useToast from "../../hooks/useToast";
import { useT } from "../../i18n/useT";
import { useAuthStore } from "../../store/auth";
import PremiumSheet from "./PremiumSheet";
import ResumePreview from "./ResumePreview";
import WizardHeader from "./WizardHeader";
import { STEPS, premiumTemplateCount, resolveTemplates } from "./data/templates";
import { useDebouncedValue } from "./lib/useDebouncedValue";
import { isStepDone, validateStep } from "./lib/validation";
import BasicStep from "./steps/BasicStep";
import EducationStep from "./steps/EducationStep";
import ExperienceStep from "./steps/ExperienceStep";
import SkillsStep from "./steps/SkillsStep";
import SummaryStep from "./steps/SummaryStep";
import TemplateStep from "./steps/TemplateStep";
import { useResumeDraft } from "./useResumeDraft";
import { useResumeSync } from "./useResumeSync";

export default function ResumeStudioPage() {
  const t = useT();
  const toast = useToast();
  const userId = useAuthStore((s) => s.user?.user_id);
  // Must run before any conditional return (Rules of Hooks).
  const keyboardOpen = useKeyboardOpen();

  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showPreview, setShowPreview] = useState(false);
  const [templateSheetOpen, setTemplateSheetOpen] = useState(false);
  const [premiumOpen, setPremiumOpen] = useState(false);

  const onDraftRestored = useCallback(() => {
    toast.info(t("resume.localDraft.restored"));
  }, [toast, t]);

  const draft = useResumeDraft(userId, onDraftRestored);
  const openPremium = useCallback(() => setPremiumOpen(true), []);
  const currentStep = STEPS[step] ?? STEPS[0];

  const sync = useResumeSync({
    userId,
    doc: draft.doc,
    fingerprint: draft.fingerprint,
    dirtyRef: draft.dirtyRef,
    localDraftAtRef: draft.localDraftAtRef,
    currentStep: currentStep.id,
    applyServer: draft.applyServer,
    markSynced: draft.markSynced,
    onPremiumBlocked: openPremium,
  });

  const templates = useMemo(
    () => resolveTemplates(t, sync.templatesQuery.data),
    [t, sync.templatesQuery.data],
  );
  const activeTemplate = templates.find((item) => item.id === draft.selectedTemplate) || templates[0];

  const { accentColor, setAccentColor } = draft;

  // Keep the accent inside the active template's palette (silently: picking a
  // template already marked the draft dirty).
  useEffect(() => {
    if (!activeTemplate) return;
    if (!activeTemplate.supports_color) {
      setAccentColor(activeTemplate.palette[0] || "#111827", true);
      return;
    }
    if (activeTemplate.palette.length > 0 && !activeTemplate.palette.includes(accentColor)) {
      setAccentColor(activeTemplate.palette[0], true);
    }
  }, [activeTemplate, accentColor, setAccentColor]);

  // Telegram's webview does not scroll a focused field into view by itself.
  useEffect(() => {
    const onFocusIn = (event: FocusEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      const tag = target.tagName.toLowerCase();
      if (tag !== "input" && tag !== "textarea" && tag !== "select") return;
      // Fields inside a sheet sit in a fixed overlay — scrolling the page would
      // move the wrong thing.
      if (target.closest('[role="dialog"]')) return;
      setTimeout(() => target.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
      setTimeout(() => target.scrollIntoView({ block: "center", behavior: "smooth" }), 260);
    };
    document.addEventListener("focusin", onFocusIn);
    return () => document.removeEventListener("focusin", onFocusIn);
  }, []);

  // Telegram BackButton: close the sheet, then the keyboard, then step back.
  useEffect(() => {
    if (step === 0 && !templateSheetOpen) {
      clearBackInterceptor();
      return;
    }
    setBackInterceptor(() => {
      if (templateSheetOpen) {
        setTemplateSheetOpen(false);
        return true;
      }
      const active = document.activeElement as HTMLElement | null;
      if (active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName)) {
        active.blur();
        return true;
      }
      setStep((previous) => Math.max(previous - 1, 0));
      return true;
    });
    return () => clearBackInterceptor();
  }, [step, templateSheetOpen]);

  const previewDoc = useDebouncedValue(draft.doc, 280);
  const previewTemplateName =
    templates.find((item) => item.id === previewDoc.selectedTemplate)?.title ?? "";

  const goNext = () => {
    const nextErrors = validateStep(currentStep.id, draft.doc, t);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    setStep((previous) => Math.min(previous + 1, STEPS.length - 1));
  };

  const doneCount = STEPS.filter((item) => isStepDone(item.id, draft.doc)).length;
  const progressPct = Math.round((doneCount / STEPS.length) * 100);
  const isLastStep = step === STEPS.length - 1;
  const StepIcon = currentStep.icon;
  const stepProps = { draft, errors };

  if (sync.authHintAvailable && sync.profileQuery.isLoading && !sync.hydratedRef.current) {
    return (
      <div className="flex items-center justify-center gap-3 py-20 text-muted">
        <Loader2 size={20} className="animate-spin" />
        <span className="text-sm">{t("common.loading")}</span>
      </div>
    );
  }

  // With the keyboard up BottomNav hides itself, so no space is reserved for it.
  const bottomClearance = keyboardOpen ? "0px" : "calc(3.5rem + var(--bottom-safe, 0px))";

  return (
    <div
      className="flex flex-col overflow-x-hidden bg-bg"
      style={{
        height: "var(--tg-viewport-height, var(--app-viewport-height, 100dvh))",
        paddingBottom: bottomClearance,
      }}
    >
      <WizardHeader
        steps={STEPS.map((item) => ({
          id: item.id,
          label: t(item.labelKey),
          done: isStepDone(item.id, draft.doc),
        }))}
        current={step}
        onStepClick={setStep}
        progressPct={progressPct}
        syncStatus={sync.syncStatus}
        previewOpen={showPreview}
        onTogglePreview={() => setShowPreview((previous) => !previous)}
      />

      {/* ── Draft banners ──────────────────────────────────────────────────── */}
      {sync.conflict && (
        <div className="border-b border-warning/40 bg-warning/10 px-4 py-2.5">
          <p className="text-xs font-semibold text-text">{t("resume.conflict.title")}</p>
          <p className="mt-0.5 text-xs text-muted">{t("resume.conflict.body")}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primaryFg"
              onClick={sync.loadFromServer}
            >
              {t("resume.conflict.reload")}
            </button>
            <button
              type="button"
              className="rounded-xl border border-border px-3 py-1.5 text-xs font-semibold text-muted"
              onClick={sync.keepLocal}
            >
              {t("resume.conflict.keepMine")}
            </button>
          </div>
        </div>
      )}

      {sync.serverDraftAvailable && !sync.conflict && (
        <div className="flex items-start gap-2 border-b border-primary/30 bg-primary/10 px-4 py-2.5">
          <FileText size={14} className="mt-0.5 shrink-0 text-primary" />
          <p className="flex-1 text-xs text-text">
            {t("resume.serverDraft.text")}{" "}
            <button type="button" className="font-semibold underline" onClick={sync.loadFromServer}>
              {t("resume.serverDraft.load")}
            </button>
          </p>
        </div>
      )}

      {/* ── Content ────────────────────────────────────────────────────────── */}
      <div className="min-h-0 flex-1 overflow-y-auto pb-2">
        <div className="flex items-center gap-3 px-4 pb-3 pt-4">
          <div className="shrink-0 rounded-2xl border border-primary/20 bg-primary/10 p-2.5">
            <StepIcon size={20} className="text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-bold text-text">{t(currentStep.labelKey)}</h2>
            <p className="mt-0.5 truncate text-xs text-muted">{t(currentStep.hintKey)}</p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[11px] font-semibold text-muted">
              {t("resume.stepOf", { step: step + 1, total: STEPS.length })}
            </p>
            <p className="text-[11px] font-bold text-success">{progressPct}%</p>
          </div>
        </div>

        {/* `key` re-mounts the subtree so the slide-in animation replays. */}
        <div key={`step-${step}`} className="step-enter space-y-4 px-4">
          {currentStep.id === "basic" && <BasicStep {...stepProps} />}
          {currentStep.id === "experience" && <ExperienceStep {...stepProps} />}
          {currentStep.id === "education" && <EducationStep {...stepProps} />}
          {currentStep.id === "skills" && <SkillsStep {...stepProps} />}
          {currentStep.id === "summary" && <SummaryStep {...stepProps} />}
          {currentStep.id === "template" && (
            <TemplateStep
              {...stepProps}
              templates={templates}
              activeTemplate={activeTemplate}
              isPro={sync.isPro}
              sheetOpen={templateSheetOpen}
              onSheetOpenChange={setTemplateSheetOpen}
              onPremiumBlocked={openPremium}
              previewDoc={previewDoc}
              onSend={() => sync.send()}
              sending={sync.sending}
              busy={sync.isBusy}
            />
          )}

          {showPreview && !isLastStep && (
            <div className="pt-2">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                {t("resume.previewLive")}
              </p>
              <ResumePreview
                profile={previewDoc.profile}
                accentColor={previewDoc.accentColor}
                templateName={previewTemplateName}
              />
            </div>
          )}
        </div>
      </div>

      {/* ── Action bar ─────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-t border-border bg-surface px-3 py-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-label={t("resume.action.back")}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border transition-colors ${
              step === 0 ? "cursor-default text-muted/50" : "text-text"
            }`}
            onClick={() => setStep((previous) => Math.max(previous - 1, 0))}
            disabled={step === 0 || sync.isBusy}
          >
            <ChevronLeft size={18} />
          </button>

          <button
            type="button"
            className={`flex h-10 flex-1 items-center justify-center gap-1.5 rounded-xl border text-xs font-semibold transition-all ${
              sync.saving
                ? "border-warning/40 bg-warning/10 text-warning"
                : draft.dirty
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border bg-surfaceAlt text-muted"
            }`}
            onClick={() => sync.save()}
            disabled={sync.isBusy}
          >
            {sync.saving ? (
              <>
                <Loader2 size={12} className="animate-spin" /> {t("resume.action.saving")}
              </>
            ) : draft.dirty ? (
              t("resume.action.save")
            ) : (
              <>
                <Check size={12} /> {t("resume.action.saved")}
              </>
            )}
          </button>

          {!isLastStep ? (
            <button
              type="button"
              className="flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-primary px-4 text-sm font-bold text-primaryFg shadow disabled:opacity-50"
              onClick={goNext}
              disabled={sync.isBusy}
            >
              {t("resume.action.next")} <ChevronRight size={16} />
            </button>
          ) : (
            <button
              type="button"
              className="flex h-10 shrink-0 items-center gap-1.5 rounded-xl bg-success px-4 text-sm font-bold text-white shadow disabled:opacity-50"
              onClick={() => sync.send()}
              disabled={sync.isBusy}
            >
              <Send size={14} /> {t("resume.send.short")}
            </button>
          )}
        </div>
      </div>

      <BottomNav />

      <PremiumSheet
        open={premiumOpen}
        onClose={() => setPremiumOpen(false)}
        premiumCount={premiumTemplateCount(templates)}
      />
    </div>
  );
}
