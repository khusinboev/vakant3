import { Link } from "react-router-dom";
import { AlertCircle, Check, Eye, FileText, Loader2 } from "lucide-react";

import WizardProgress, { type WizardStep } from "../../components/ui/WizardProgress";
import { useT } from "../../i18n/useT";
import type { TranslationKey } from "../../i18n";
import type { SyncStatus } from "./useResumeSync";

const SYNC_LABEL_KEYS: Record<SyncStatus, TranslationKey> = {
  idle: "resume.sync.idle",
  saving: "resume.sync.saving",
  synced: "resume.sync.synced",
  error: "resume.sync.error",
};

const SYNC_TEXT_CLS: Record<SyncStatus, string> = {
  idle: "text-muted",
  saving: "text-warning",
  synced: "text-success",
  error: "text-danger",
};

export type WizardHeaderProps = {
  steps: WizardStep[];
  current: number;
  onStepClick: (index: number) => void;
  progressPct: number;
  syncStatus: SyncStatus;
  previewOpen: boolean;
  onTogglePreview: () => void;
};

/** Sticky top bar: brand, sync state, step dots and the completion bar. */
export default function WizardHeader({
  steps,
  current,
  onStepClick,
  progressPct,
  syncStatus,
  previewOpen,
  onTogglePreview,
}: WizardHeaderProps) {
  const t = useT();

  return (
    <div className="sticky top-0 z-20 shrink-0 border-b border-border bg-surface shadow-sm">
      <div
        className="flex items-center justify-center border-b border-border"
        style={{
          paddingTop: "calc(0.75rem + var(--tg-content-safe-area-top, 0px))",
          paddingBottom: "0.625rem",
        }}
      >
        <Link to="/app" className="font-display text-xl font-extrabold text-primary">
          {t("app.name")}
        </Link>
      </div>

      <div className="flex items-center justify-between px-4 pb-1.5 pt-2">
        <div className="flex items-center gap-2">
          <FileText size={15} className="shrink-0 text-primary" />
          <span className="text-sm font-bold text-text">{t("resume.title")}</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-pressed={previewOpen}
            className="flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-primary"
            onClick={onTogglePreview}
          >
            <Eye size={13} />
            <span>{t("resume.preview")}</span>
          </button>
          <span className={`flex items-center gap-1 text-[10px] font-semibold ${SYNC_TEXT_CLS[syncStatus]}`}>
            {syncStatus === "saving" ? (
              <Loader2 size={10} className="animate-spin" />
            ) : syncStatus === "synced" ? (
              <Check size={10} />
            ) : syncStatus === "error" ? (
              <AlertCircle size={10} />
            ) : null}
            {t(SYNC_LABEL_KEYS[syncStatus])}
          </span>
        </div>
      </div>

      <WizardProgress steps={steps} current={current} onStepClick={onStepClick} />

      <div className="h-[3px] bg-surfaceAlt">
        <div
          className="h-full bg-success transition-all duration-700 ease-out"
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </div>
  );
}
