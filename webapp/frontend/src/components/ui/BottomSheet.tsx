import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

export type BottomSheetProps = {
  open: boolean;
  onClose: () => void;
  /** Rendered in the sticky header and wired to aria-labelledby. */
  title?: ReactNode;
  /** Small line under the title. */
  subtitle?: ReactNode;
  children?: ReactNode;
  /** Sticky footer (action buttons). Gets the bottom safe-area padding. */
  footer?: ReactNode;
  /** Tailwind max-height for the panel. Default "max-h-[85dvh]". */
  maxHeightClass?: string;
  /** Extra classes on the panel. */
  className?: string;
  /** Show the little drag handle. Default true. */
  showHandle?: boolean;
  /** Close when the backdrop is tapped. Default true. */
  closeOnBackdrop?: boolean;
  /** Accessible name when no visible `title` is given. */
  ariaLabel?: string;
};

/**
 * The single bottom-sheet primitive for the app.
 * Portal + body scroll lock + role="dialog"/aria-modal + Esc + backdrop click,
 * and it moves focus into the panel on open.
 *
 *   <BottomSheet open={open} onClose={close} title={t("profile.notifSettings")}>
 *     …body…
 *   </BottomSheet>
 */
export default function BottomSheet({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  maxHeightClass = "max-h-[85dvh]",
  className = "",
  showHandle = true,
  closeOnBackdrop = true,
  ariaLabel,
}: BottomSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  // Esc to close.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  // Lock background scroll while the sheet is up.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Move focus into the sheet so Esc and screen readers work immediately.
  useEffect(() => {
    if (!open) return;
    const node = panelRef.current;
    if (!node) return;
    const focusable = node.querySelector<HTMLElement>(
      "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])",
    );
    (focusable ?? node).focus({ preventScroll: true });
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={closeOnBackdrop ? onClose : undefined}
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ? undefined : ariaLabel}
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        className={`relative flex ${maxHeightClass} flex-col overflow-hidden rounded-t-3xl border border-b-0 border-border bg-surface text-text shadow-2xl outline-none md:mx-auto md:mb-6 md:w-[42rem] md:rounded-3xl md:border-b ${className}`}
      >
        {showHandle && (
          <div className="flex shrink-0 justify-center pb-1 pt-3">
            <div className="h-1 w-10 rounded-full bg-border" />
          </div>
        )}

        {(title || subtitle) && (
          <div className="shrink-0 border-b border-border px-5 pb-3 pt-1">
            {title && (
              <h2 id={titleId} className="text-base font-semibold leading-tight text-text">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
          </div>
        )}

        <div
          className="flex-1 overflow-y-auto px-5 py-4 pl-[calc(1.25rem+var(--tg-content-safe-area-left))] pr-[calc(1.25rem+var(--tg-content-safe-area-right))]"
          style={footer ? undefined : { paddingBottom: "calc(1rem + var(--bottom-safe, 0px))" }}
        >
          {children}
        </div>

        {footer && (
          <div
            className="shrink-0 border-t border-border px-5 pt-3"
            style={{ paddingBottom: "calc(0.75rem + var(--bottom-safe, 0px))" }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}
