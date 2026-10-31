import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import BottomSheet from "../../../components/ui/BottomSheet";
import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { useIsDesktopSm } from "../hooks/useMediaQuery";
import { useHistorySheet, type HistorySheet } from "../hooks/useHistorySheet";

export type SheetSize = "auto" | "full";

export type SheetFrameProps = {
  open: boolean;
  onClose: () => void;
  titleKey?: TranslationKey;
  title?: ReactNode;
  subtitle?: ReactNode;
  /** Sticky footer, e.g. Apply / Clear. */
  footer?: ReactNode;
  size?: SheetSize;
  children?: ReactNode;
  ariaLabel?: string;
};

/**
 * The presentational overlay: a bottom sheet on phones, a centered modal from
 * 768px. Use `Sheet` (below) unless you already own the open/close state —
 * every overlay in the panel must be a history entry.
 */
export function SheetFrame({
  open,
  onClose,
  titleKey,
  title,
  subtitle,
  footer,
  size = "auto",
  children,
  ariaLabel,
}: SheetFrameProps) {
  const t = useT();
  const isWide = useIsDesktopSm();
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const heading = titleKey ? t(titleKey) : title;

  useEffect(() => {
    if (!open || !isWide) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, isWide, onClose]);

  useEffect(() => {
    if (!open || !isWide) return;
    const node = panelRef.current;
    const focusable = node?.querySelector<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
    );
    (focusable ?? node)?.focus({ preventScroll: true });
  }, [open, isWide]);

  if (!open) return null;

  if (!isWide) {
    return (
      <BottomSheet
        open={open}
        onClose={onClose}
        title={heading}
        subtitle={subtitle}
        footer={footer}
        ariaLabel={ariaLabel}
        maxHeightClass={size === "full" ? "max-h-[95dvh] h-[95dvh]" : "max-h-[85dvh]"}
      >
        {children}
      </BottomSheet>
    );
  }

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3">
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={heading ? undefined : ariaLabel}
        aria-labelledby={heading ? titleId : undefined}
        tabIndex={-1}
        className={`admin-root relative flex w-full max-w-lg flex-col overflow-hidden rounded-xl border border-border bg-surface text-text shadow-2xl outline-none ${
          size === "full" ? "h-[85dvh]" : "max-h-[85dvh]"
        }`}
      >
        {(heading || subtitle) && (
          <div className="flex shrink-0 items-start gap-2 border-b border-border px-3 py-2">
            <div className="min-w-0 flex-1">
              {heading && (
                <h2 id={titleId} className="truncate text-[15px] font-semibold leading-tight">
                  {heading}
                </h2>
              )}
              {subtitle && <p className="mt-0.5 truncate text-[11px] text-muted">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("admin.sheet.close")}
              className="-mr-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-muted hover:bg-surfaceAlt hover:text-text"
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">{children}</div>

        {footer && <div className="shrink-0 border-t border-border px-3 py-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export type SheetProps = Omit<SheetFrameProps, "open" | "onClose"> & {
  /** Unique name; it is what travels in `history.state.sheets`. */
  name: string;
  /** Called when the sheet is dismissed (back, Esc, backdrop, ×). */
  onClose?: () => void;
};

/**
 * A history-backed overlay.
 *
 *   const sheet = useHistorySheet("channels.add");
 *   <Button labelKey="adminChannels.add" onClick={() => sheet.openSheet()} />
 *   <Sheet name="channels.add" titleKey="adminChannels.add">…</Sheet>
 *
 * Back / Esc / the header ‹ all pop exactly this sheet.
 */
export function Sheet({ name, onClose, children, ...rest }: SheetProps) {
  const sheet: HistorySheet = useHistorySheet(name);
  return (
    <SheetFrame
      {...rest}
      open={sheet.open}
      onClose={() => {
        onClose?.();
        sheet.close();
      }}
    >
      {children}
    </SheetFrame>
  );
}

export default Sheet;
