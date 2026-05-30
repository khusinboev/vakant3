import { useState, useEffect } from "react";

/**
 * Returns true while a soft keyboard is likely open.
 * Detected via focusin/focusout on input/textarea/select elements.
 * Shared by BottomNav and any page that needs to react to keyboard state.
 */
export function useKeyboardOpen(): boolean {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const show = (e: FocusEvent) => {
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") {
        setOpen(true);
      }
    };
    // Small delay on hide so we don't flicker between two focused fields
    const hide = () => setTimeout(() => setOpen(false), 150);

    document.addEventListener("focusin", show);
    document.addEventListener("focusout", hide);
    return () => {
      document.removeEventListener("focusin", show);
      document.removeEventListener("focusout", hide);
    };
  }, []);

  return open;
}
