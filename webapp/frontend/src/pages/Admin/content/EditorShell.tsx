import { useEffect, type ReactNode } from "react";
import { ArrowLeft, Save, Trash2 } from "lucide-react";

import { useT } from "../../../i18n/useT";
import { requestConfirm } from "../hooks/useConfirm";
import { setContentDirty } from "./dirtyGuard";

export type EditorShellProps = {
  title: string;
  dirty: boolean;
  saving: boolean;
  onBack: () => void;
  onSave: () => void;
  saveDisabled?: boolean;
  onDelete?: () => void;
  deleting?: boolean;
  children: ReactNode;
};

/**
 * Chrome shared by the article/tip/category editors: a back button that asks
 * before discarding unsaved work, a save button, an optional delete button,
 * and a full-height scroll area for the form itself.
 */
export default function EditorShell({
  title,
  dirty,
  saving,
  onBack,
  onSave,
  saveDisabled = false,
  onDelete,
  deleting = false,
  children,
}: EditorShellProps) {
  const t = useT();

  // Feed `ContentPage`'s sub-tab switch guard (see dirtyGuard.ts).
  useEffect(() => {
    setContentDirty(dirty);
    return () => setContentDirty(false);
  }, [dirty]);

  const handleBack = async () => {
    if (dirty) {
      const ok = await requestConfirm({
        titleKey: "adminContent.editor.discardTitle",
        descriptionKey: "adminContent.editor.discardDesc",
        confirmLabelKey: "adminContent.editor.discardConfirm",
        danger: true,
      });
      if (!ok) return;
    }
    setContentDirty(false);
    onBack();
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    const ok = await requestConfirm({
      titleKey: "adminContent.editor.deleteTitle",
      descriptionKey: "adminContent.editor.deleteDesc",
      descriptionVars: { id: title },
      confirmLabelKey: "adminContent.editor.deleteConfirm",
      danger: true,
    });
    if (!ok) return;
    onDelete();
  };

  return (
    <div className="flex min-h-[calc(var(--app-viewport-height)-9rem)] flex-col">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <button
            type="button"
            onClick={() => void handleBack()}
            aria-label={t("adminContent.editor.backToList")}
            title={t("adminContent.editor.backToList")}
            className="tap-target rounded-xl border border-border bg-surface p-2 text-muted transition-colors hover:text-text"
          >
            <ArrowLeft size={16} aria-hidden="true" />
          </button>
          <h2 className="min-w-0 truncate text-base font-semibold text-text">{title}</h2>
          {dirty && (
            <span className="shrink-0 rounded-full bg-warning/10 px-2 py-0.5 text-[11px] font-semibold text-warning">
              {t("adminContent.editor.unsavedBadge")}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {onDelete && (
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={deleting}
              className="tap-target inline-flex items-center gap-1.5 rounded-xl border border-danger/40 px-3 py-2 text-xs font-semibold text-danger transition-colors hover:bg-danger/10 disabled:opacity-60"
            >
              <Trash2 size={14} aria-hidden="true" />
              {t("adminContent.editor.delete")}
            </button>
          )}
          <button
            type="button"
            onClick={onSave}
            disabled={saving || saveDisabled}
            className="tap-target inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-2 text-xs font-semibold text-primaryFg disabled:opacity-60"
          >
            <Save size={14} aria-hidden="true" />
            {saving ? t("adminContent.editor.saving") : t("adminContent.editor.save")}
          </button>
        </div>
      </header>
      <div className="flex-1 space-y-4">{children}</div>
    </div>
  );
}
