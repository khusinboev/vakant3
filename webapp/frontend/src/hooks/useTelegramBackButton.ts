import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { hasOpenSheet } from "../pages/Admin/hooks/useHistorySheet";
import { VACANCY_QUERY_KEY } from "../lib/deepLink";
import { isAdminPath, parentOf } from "../lib/nav/parents";
import { backAction, useNavRecorder } from "./useAppBack";

function isTyping(el: Element | null): boolean {
  const tag = (el as HTMLElement | null)?.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

/**
 * Shows / hides Telegram's native back button and routes its press into the
 * single Back model (`useAppBack.backAction`, parents in `lib/nav/parents.ts`).
 *
 *  - An input has focus -> blur it (dismiss the keyboard) and stop.
 *  - Otherwise `backAction`: open history overlay -> page interceptor -> parent.
 *  - Esc stays with the overlays that own it (BottomSheet, the admin shell).
 *  - The button is hidden only on Home with nothing open, so Telegram's own
 *    close then leaves the app. The admin panel always shows it (spec §1.1).
 */
export default function useTelegramBackButton() {
  const navigate = useNavigate();
  const location = useLocation();
  useNavRecorder();

  useEffect(() => {
    const btn = window.Telegram?.WebApp?.BackButton;

    // An open vacancy sheet on Home (`/app?vacancy=<uid>`) is one level deep:
    // Home's interceptor closes it.
    const overlay =
      hasOpenSheet(location) ||
      (location.pathname === "/app" && new URLSearchParams(location.search).has(VACANCY_QUERY_KEY));
    const isRoot = !overlay && !isAdminPath(location.pathname) && !parentOf(location.pathname, location.state);

    const handleBack = () => {
      if (isTyping(document.activeElement)) {
        (document.activeElement as HTMLElement).blur();
        return;
      }
      backAction(navigate, location);
    };

    if (btn) {
      if (isRoot) {
        btn.hide();
      } else {
        btn.show();
        btn.onClick(handleBack);
      }
    }

    return () => {
      btn?.offClick(handleBack);
    };
  }, [location, navigate]);
}
