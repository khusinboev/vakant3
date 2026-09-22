import { useCallback, useMemo } from "react";
import { useLocation, useNavigate, type Location } from "react-router-dom";

/**
 * Every overlay in the admin panel is a history entry.
 *
 * Opening a sheet pushes the *same* location again with one more name on
 * `location.state.sheets`; closing it is `history.back()`. That single rule is
 * what makes the Telegram BackButton, the browser back gesture, `Esc` and the
 * header's ‹ button all close exactly one level (see `useAdminBack`).
 *
 *   const sheet = useHistorySheet("users.balance");
 *   <Button onClick={() => sheet.openSheet({ userId })} .../>
 *   <Sheet name="users.balance" titleKey="adminUsers.balance.title">…</Sheet>
 */
export type AdminLocationState = {
  sheets?: string[];
  sheetPayloads?: Record<string, unknown>;
} | null;

export type HistorySheet<P = unknown> = {
  /** `true` while this sheet is anywhere on the stack. */
  open: boolean;
  /** `true` when it is the entry the next "back" will pop. */
  topmost: boolean;
  /** Whatever `openSheet(payload)` was called with. */
  payload: P | undefined;
  openSheet: (payload?: P) => void;
  /** Pops this sheet — a no-op unless it is the topmost one. */
  close: () => void;
};

/** The open sheet names of a router location, oldest first. */
export function sheetsFromState(state: unknown): string[] {
  const sheets = (state as AdminLocationState)?.sheets;
  return Array.isArray(sheets) ? sheets : [];
}

/** `true` when the location has at least one overlay on it. */
export function hasOpenSheet(location: Pick<Location, "state">): boolean {
  return sheetsFromState(location.state).length > 0;
}

export function useHistorySheet<P = unknown>(name: string): HistorySheet<P> {
  const location = useLocation();
  const navigate = useNavigate();

  const sheets = sheetsFromState(location.state);
  const open = sheets.includes(name);
  const topmost = sheets[sheets.length - 1] === name;
  const payload = ((location.state as AdminLocationState)?.sheetPayloads ?? {})[name] as
    | P
    | undefined;

  const openSheet = useCallback(
    (next?: P) => {
      const state = (location.state ?? {}) as Record<string, unknown>;
      const current = sheetsFromState(location.state);
      if (current[current.length - 1] === name) return;
      navigate(`${location.pathname}${location.search}`, {
        state: {
          ...state,
          sheets: [...current.filter((sheet) => sheet !== name), name],
          sheetPayloads: {
            ...((state.sheetPayloads as Record<string, unknown>) ?? {}),
            [name]: next,
          },
        },
      });
    },
    [location.pathname, location.search, location.state, name, navigate],
  );

  const close = useCallback(() => {
    if (sheetsFromState(location.state).slice(-1)[0] !== name) return;
    navigate(-1);
  }, [location.state, name, navigate]);

  return useMemo(
    () => ({ open, topmost, payload, openSheet, close }),
    [open, topmost, payload, openSheet, close],
  );
}

export default useHistorySheet;
