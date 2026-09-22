import { AlertTriangle } from "lucide-react";

import type { TranslationKey, TranslationVars } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import Button from "../ui/Button";
import { SheetFrame } from "../ui/Sheet";

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
 * The confirmation dialog, built on `SheetFrame` (bottom sheet on phones,
 * centered modal from 768px).
 *
 * Normally driven by `useConfirmedMutation` through `<ConfirmDialogHost/>`,
 * which is the part that makes it a history entry — back closes it.
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

  return (
    <SheetFrame
      open={open}
      onClose={loading ? () => undefined : onClose}
      titleKey={titleKey}
      footer={
        <div className="flex gap-2">
          <Button
            size="md"
            variant="secondary"
            labelKey={cancelLabelKey}
            disabled={loading}
            onClick={onClose}
          />
          <Button
            size="md"
            full
            variant={danger ? "danger" : "primary"}
            labelKey={loading ? "admin.confirm.working" : confirmLabelKey}
            disabled={loading}
            loading={loading}
            onClick={onConfirm}
          />
        </div>
      }
    >
      <div className="flex items-start gap-2">
        {danger && (
          <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
            <AlertTriangle size={14} aria-hidden="true" />
          </span>
        )}
        <p className="min-w-0 flex-1 text-[13px] text-muted">
          {descriptionKey ? t(descriptionKey, descriptionVars) : t("admin.confirm.title")}
        </p>
      </div>
    </SheetFrame>
  );
}
