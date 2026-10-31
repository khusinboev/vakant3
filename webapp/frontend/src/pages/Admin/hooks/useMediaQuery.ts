import { useSyncExternalStore } from "react";

/**
 * Reactive `matchMedia`. Used by the admin shell to pick the desktop layout
 * and by `ConfirmDialog` to choose between a centered modal and a BottomSheet.
 *
 * A media query is not React state, so `useSyncExternalStore` is the right
 * primitive here: no effect, no first-paint flash.
 */
export function useMediaQuery(query: string): boolean {
  const subscribe = (onChange: () => void) => {
    const mql = window.matchMedia?.(query);
    mql?.addEventListener?.("change", onChange);
    return () => mql?.removeEventListener?.("change", onChange);
  };
  const getSnapshot = () => window.matchMedia?.(query)?.matches ?? false;
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

/** Tailwind `md` — the DataTable switches to cards below this. */
export const useIsDesktopSm = () => useMediaQuery("(min-width: 768px)");
/** Tailwind `lg` — the admin shell switches from bottom tabs to a sidebar. */
export const useIsDesktop = () => useMediaQuery("(min-width: 1024px)");

export default useMediaQuery;
