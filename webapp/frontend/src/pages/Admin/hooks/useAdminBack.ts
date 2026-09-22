import { useCallback, useMemo } from "react";
import {
  useLocation,
  useNavigate,
  type Location,
  type NavigateFunction,
} from "react-router-dom";

import { sheetsFromState } from "./useHistorySheet";

/** Where "back" lands when there is nothing left to pop inside the panel. */
export const ADMIN_EXIT_PATH = "/app";

/**
 * One level back, wherever the press came from (Telegram BackButton, browser
 * back, `Esc`, the header's ‹).
 *
 *  1. an overlay is open  -> pop it (it is a history entry);
 *  2. some in-app history -> `navigate(-1)`;
 *  3. nothing before us   -> leave the panel for `/app`.
 */
export function adminBackAction(navigate: NavigateFunction, location: Location): void {
  if (sheetsFromState(location.state).length > 0) {
    navigate(-1);
    return;
  }

  // React Router keeps its position in `window.history.state.idx`; 0 means the
  // panel is the first entry of this session, so `-1` would leave the app.
  const idx = (window.history.state as { idx?: number } | null)?.idx;
  if (typeof idx === "number" && idx > 0) {
    navigate(-1);
    return;
  }

  navigate(ADMIN_EXIT_PATH, { replace: true });
}

export type AdminBack = { back: () => void };

export function useAdminBack(): AdminBack {
  const navigate = useNavigate();
  const location = useLocation();
  const back = useCallback(() => adminBackAction(navigate, location), [navigate, location]);
  return useMemo(() => ({ back }), [back]);
}

export default useAdminBack;
