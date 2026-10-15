import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { adminBackAction } from "../pages/Admin/hooks/useAdminBack";
import { hasOpenSheet } from "../pages/Admin/hooks/useHistorySheet";
import { VACANCY_QUERY_KEY } from "../lib/deepLink";
import { runBackInterceptor } from "./useBackInterceptor";

/**
 * Shows / hides Telegram's native back button and decides what one press does.
 *
 * Behaviour on press:
 *  1. An input/textarea has focus -> blur it (dismiss the keyboard). Stop.
 *  2. Inside `/admin/*` -> an open overlay is popped first; otherwise a page
 *     interceptor may claim the press; otherwise `adminBackAction` (one
 *     history step, else leave the panel for `/app`). The button is always
 *     visible there (spec §1.1), including on the panel's root.
 *  3. A page-level interceptor is registered -> call it; `true` means handled.
 *  4. Default -> `navigate(-1)`.
 */
const TOP_LEVEL_PATHS = ["/app", "/saves", "/profile", "/referral", "/"];

export default function useTelegramBackButton() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const btn = window.Telegram?.WebApp?.BackButton;
    if (!btn) return;

    const isAdmin = location.pathname === "/admin" || location.pathname.startsWith("/admin/");
    // An open vacancy sheet on Home (`/app?vacancy=<uid>`) is one level deep:
    // the button is shown and Home's interceptor closes the sheet.
    const hasVacancySheet =
      location.pathname === "/app" && new URLSearchParams(location.search).has(VACANCY_QUERY_KEY);
    const isTopLevel = !isAdmin && !hasVacancySheet && TOP_LEVEL_PATHS.includes(location.pathname);

    const handleBack = () => {
      const active = document.activeElement as HTMLElement | null;
      if (
        active &&
        (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.tagName === "SELECT")
      ) {
        active.blur();
        return;
      }

      if (isAdmin) {
        // An open overlay (sheet, confirm dialog) is closed first: a page
        // interceptor such as the editor's unsaved-changes guard must not
        // re-prompt while its own dialog is the thing being dismissed.
        if (!hasOpenSheet(location) && runBackInterceptor()) return;
        adminBackAction(navigate, location);
        return;
      }

      if (runBackInterceptor()) return;
      navigate(-1);
    };

    if (isTopLevel) {
      btn.hide();
    } else {
      btn.show();
      btn.onClick(handleBack);
    }

    return () => {
      btn.offClick(handleBack);
    };
  }, [location, navigate]);
}
