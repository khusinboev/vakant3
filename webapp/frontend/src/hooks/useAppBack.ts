import { useCallback, useEffect, useMemo } from "react";
import { useLocation, useNavigate, type Location, type NavigateFunction } from "react-router-dom";

import { hasOpenSheet } from "../pages/Admin/hooks/useHistorySheet";
import { normalizePath, parentOf } from "../lib/nav/parents";
import { runBackInterceptor } from "./useBackInterceptor";

/**
 * The one "Back" of the Mini App (Telegram BackButton, Esc, the admin header's
 * ‹ and in-page back buttons all end up here).
 *
 * Back goes UP the screen hierarchy (`lib/nav/parents.ts`), never through the
 * browsing history:
 *  1. an overlay that is a history entry is open -> pop exactly that entry;
 *  2. a page interceptor (sheet / wizard step / dirty-form guard) claims it;
 *  3. otherwise go to the parent screen: `navigate(-1)` only when the entry
 *     right below us already IS the parent, else `replace` to the parent, so
 *     the stack never grows from going back and never leaves the app.
 * At the root (Home) there is nothing to do and the BackButton is hidden.
 */

type Visited = { path: string; sheets: boolean };

/** Router position (`history.state.idx`) -> what that entry showed. */
const visited = new Map<number, Visited>();

function historyIndex(): number | null {
  const idx = (window.history.state as { idx?: number } | null)?.idx;
  return typeof idx === "number" ? idx : null;
}

/** Remember the current entry; entries above it are forward history and stale. */
export function recordVisit(location: Pick<Location, "pathname" | "state">): void {
  const idx = historyIndex();
  if (idx === null) return;
  for (const key of [...visited.keys()]) if (key > idx) visited.delete(key);
  visited.set(idx, { path: normalizePath(location.pathname), sheets: hasOpenSheet(location) });
}

function previousEntryIs(path: string): boolean {
  const idx = historyIndex();
  if (idx === null || idx < 1) return false;
  const previous = visited.get(idx - 1);
  return Boolean(previous && !previous.sheets && previous.path === path);
}

/** Go to the parent screen (no overlays, no interceptors). No-op at the root. */
export function goToParent(navigate: NavigateFunction, location: Location): void {
  const parent = parentOf(location.pathname, location.state);
  if (!parent) return;
  if (previousEntryIs(parent)) navigate(-1);
  else navigate(parent, { replace: true });
}

/** One Back press (interceptors included). Returns false at the root. */
export function backAction(navigate: NavigateFunction, location: Location): boolean {
  if (hasOpenSheet(location)) {
    navigate(-1);
    return true;
  }
  if (runBackInterceptor()) return true;
  if (!parentOf(location.pathname, location.state)) return false;
  goToParent(navigate, location);
  return true;
}

/** Records the visited screens (mount once, inside the router). */
export function useNavRecorder(): void {
  const location = useLocation();
  useEffect(() => {
    recordVisit(location);
  }, [location]);
}

/** `back()` for in-page buttons that are not the Telegram BackButton. */
export default function useAppBack(): { back: () => void; goToParent: () => void } {
  const navigate = useNavigate();
  const location = useLocation();
  const back = useCallback(() => {
    backAction(navigate, location);
  }, [navigate, location]);
  const up = useCallback(() => goToParent(navigate, location), [navigate, location]);
  return useMemo(() => ({ back, goToParent: up }), [back, up]);
}
