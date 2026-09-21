import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle } from "lucide-react";

import BottomSheet from "../../../components/ui/BottomSheet";
import type { TranslationKey, TranslationVars } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useIsDesktopSm } from "../hooks/useMediaQuery";

export type ConfirmDialogProps = {
  open: boolean;
  titleKey: TranslationKey;
  descriptionKey?: TranslationKey;
  descriptionVars?: TranslationVars;
  danger?: boolean;
  confirmLabelKey?: TranslationKey;
  cancelLabelKey?: TranslationKey;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
};

/**
 * A centered modal on ≥768px, the app's `BottomSheet` below it.
 * Usually driven by `useConfirmedMutation` through `<ConfirmDialogHost/>`;
 * use it directly only for confirmations that do not need a server token.
 */
export default function ConfirmDialog({
  open,
  titleKey,
  descriptionKey,
  descriptionVars,
  danger = false,
  confirmLabelKey = "admin.confirm.confirm",
  cancelLabelKey = "admin.confirm.cancel",
  onConfirm,
  onClose,
  loading = false,
}: ConfirmDialogProps) {
  const t = useT();
  const isWide = useIsDesktopSm();
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  // Esc closes the desktop modal (BottomSheet handles its own).
  useEffect(() => {
    if (!open || !isWide) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !loading) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, isWide, loading, onClose]);

  useEffect(() => {
    if (!open || !isWide) return;
    panelRef.current?.querySelector<HTMLButtonElement>("button[data-autofocus]")?.focus();
  }, [open, isWide]);

  const confirmClass = `tap-target flex-1 rounded-xl px-4 py-2.5 text-sm font-semibold disabled:opacity-60 ${
    danger ? "bg-danger text-white" : "bg-primary text-primaryFg"
  }`;
  const cancelClass =
    "tap-target flex-1 rounded-xl border border-border bg-surface px-4 py-2.5 text-sm font-semibold text-text disabled:opacity-60";

  const body = (
    <>
      {danger && (
        <span className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-danger/10 text-danger">
          <AlertTriangle size={17} aria-hidden="true" />
        </span>
      )}
      {descriptionKey && (
        <p className="text-sm text-muted">{t(descriptionKey, descriptionVars)}</p>
      )}
    </>
  );

  const actions = (
    <div className="flex gap-2">
      <button type="button" onClick={onClose} disabled={loading} className={cancelClass}>
        {t(cancelLabelKey)}
      </button>
      <button
        type="button"
        data-autofocus
        onClick={onConfirm}
        disabled={loading}
        className={confirmClass}
      >
        {loading ? t("admin.confirm.working") : t(confirmLabelKey)}
      </button>
    </div>
  );

  if (!open) return null;

  if (!isWide) {
    return (
      <BottomSheet open={open} onClose={loading ? () => undefined : onClose} title={t(titleKey)} footer={actions}>
        {body}
      </BottomSheet>
    );
  }

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={loading ? undefined : onClose}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-sm rounded-2xl border border-border bg-surface p-5 text-text shadow-2xl"
      >
        <h2 id={titleId} className="text-base font-semibold text-text">
          {t(titleKey)}
        </h2>
        <div className="mt-3">{body}</div>
        <div className="mt-5">{actions}</div>
      </div>
    </div>,
    document.body,
  );
}
