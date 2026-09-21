import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import BottomSheet from "../../../components/ui/BottomSheet";
import { useT } from "../../../i18n/useT";
import { useIsDesktopSm } from "../hooks/useMediaQuery";

export type UserDrawerProps = {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
};

/**
 * The detail container: the app's `BottomSheet` on phones, a right-hand side
 * panel from 768px up. Same contract in both: Esc + backdrop close it, focus
 * moves inside, background scroll is locked.
 */
export default function UserDrawer({ open, onClose, title, subtitle, children }: UserDrawerProps) {
  const t = useT();
  const isWide = useIsDesktopSm();
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  const desktop = open && isWide;

  useEffect(() => {
    if (!desktop) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [desktop, onClose]);

  useEffect(() => {
    if (!desktop) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [desktop]);

  useEffect(() => {
    if (!desktop) return;
    panelRef.current?.focus();
  }, [desktop]);

  if (!open) return null;

  if (!isWide) {
    return (
      <BottomSheet open={open} onClose={onClose} title={title} subtitle={subtitle}>
        {children}
      </BottomSheet>
    );
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-black/40"
        aria-hidden="true"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <h2 id={titleId} className="truncate text-sm font-semibold text-text">
              {title}
            </h2>
            {subtitle && <p className="truncate text-xs text-muted">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("adminUsers.detail.close")}
            className="tap-target shrink-0 rounded-xl border border-border bg-surfaceAlt p-1.5 text-muted hover:text-text"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
