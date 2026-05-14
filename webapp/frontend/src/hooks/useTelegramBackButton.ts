import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * Shows / hides Telegram's native back button (in the app header) depending
 * on whether the user is on the root page or a deeper route.
 *
 * Root pages (/app, /saves, /profile, /referral) are considered "top-level",
 * so the back button is hidden there.  Any sub-route (e.g. a vacancy detail
 * page) will show the back button and navigate(-1) when tapped.
 *
 * Also responds to the Android hardware back button via the same callback.
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
