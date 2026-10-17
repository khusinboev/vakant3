import { useState, useEffect } from "react";

/**
 * Returns true while a soft keyboard is likely open.
 * Detected via focusin/focusout on input/textarea/select elements.
 * Shared by BottomNav and any page that needs to react to keyboard state.
 */
export function useKeyboardOpen(): boolean {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let hideTimer: ReturnType<typeof setTimeout> | undefined;

    const show = (e: FocusEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") {
        // A focus move between two fields fires focusout then focusin: cancel
        // the pending hide so the nav does not flicker.
        if (hideTimer) clearTimeout(hideTimer);
        setOpen(true);
      }
    };

    // Small delay on hide so we don't flicker between two focused fields
    const hide = () => {
      if (hideTimer) clearTimeout(hideTimer);
      hideTimer = setTimeout(() => setOpen(false), 150);
    };

    document.addEventListener("focusin", show);
    document.addEventListener("focusout", hide);
    return () => {
      if (hideTimer) clearTimeout(hideTimer);
      document.removeEventListener("focusin", show);
      document.removeEventListener("focusout", hide);
    };
  }, []);

  return open;
}
