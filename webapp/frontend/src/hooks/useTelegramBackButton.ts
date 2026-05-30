import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { runBackInterceptor } from "./useBackInterceptor";

/**
 * Shows / hides Telegram's native back button (in the app header) depending
 * on whether the user is on the root page or a deeper route.
 *
 * Behaviour on press:
 *  1. If an input/textarea has focus → blur it (dismiss keyboard). Stop.
 *  2. If a page-level interceptor is registered → call it. If it returns
 *     true the interceptor handled the action (e.g. wizard step back). Stop.
 *  3. Default → navigate(-1).
 */
const TOP_LEVEL_PATHS = ["/app", "/saves", "/profile", "/referral", "/"];

export default function useTelegramBackButton() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const btn = window.Telegram?.WebApp?.BackButton;
    if (!btn) return;

    const isTopLevel = TOP_LEVEL_PATHS.includes(location.pathname);

    const handleBack = () => {
      // 1. Close keyboard / blur focused input first
      const active = document.activeElement as HTMLElement | null;
      if (
        active &&
        (active.tagName === "INPUT" ||
          active.tagName === "TEXTAREA" ||
          active.tagName === "SELECT")
      ) {
        active.blur();
        return;
      }

      // 2. Page-level interceptor (e.g. wizard step navigation)
      if (runBackInterceptor()) return;

      // 3. Default navigation
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
  }, [location.pathname, navigate]);
}
