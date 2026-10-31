import { useCallback, useMemo } from "react";
import {
  useLocation,
  useNavigate,
  type Location,
  type NavigateFunction,
} from "react-router-dom";

import { goToParent } from "../../../hooks/useAppBack";
import { HOME_PATH } from "../../../lib/nav/parents";
import { sheetsFromState } from "./useHistorySheet";

/** Where "back" lands from the panel's root. */
export const ADMIN_EXIT_PATH = HOME_PATH;

/**
 * One level back, wherever the press came from (Telegram BackButton, browser
 * back, `Esc`, the header's ‹), following the app-wide model of `useAppBack`:
 *
 *  1. an overlay is open -> pop it (it is a history entry);
 *  2. otherwise go UP: a sub-page to its parent page (`parentOf`), the panel's
 *     root to `/app` — never through every filter / tab change that happened
 *     inside a page (those replace their history entry).
 */
export function adminBackAction(navigate: NavigateFunction, location: Location): void {
  if (sheetsFromState(location.state).length > 0) {
    navigate(-1);
    return;
  }
  goToParent(navigate, location);
}

export type AdminBack = { back: () => void };

export function useAdminBack(): AdminBack {
  const navigate = useNavigate();
  const location = useLocation();
  const back = useCallback(() => adminBackAction(navigate, location), [navigate, location]);
  return useMemo(() => ({ back }), [back]);
}

export default useAdminBack;
