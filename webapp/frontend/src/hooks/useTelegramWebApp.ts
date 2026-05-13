import { useEffect } from "react";

function px(value: number | undefined): string {
  return `${Math.max(0, Number(value ?? 0))}px`;
}

function setInsetVariables(webApp: TelegramWebApp) {
  const root = document.documentElement;
  const safe = webApp.safeAreaInset;
  const contentSafe = webApp.contentSafeAreaInset;

  root.style.setProperty("--tg-safe-area-top", px(safe?.top));
  root.style.setProperty("--tg-safe-area-bottom", px(safe?.bottom));
  root.style.setProperty("--tg-safe-area-left", px(safe?.left));
  root.style.setProperty("--tg-safe-area-right", px(safe?.right));

  root.style.setProperty("--tg-content-safe-area-top", px(contentSafe?.top));
  root.style.setProperty("--tg-content-safe-area-bottom", px(contentSafe?.bottom));
  root.style.setProperty("--tg-content-safe-area-left", px(contentSafe?.left));
  root.style.setProperty("--tg-content-safe-area-right", px(contentSafe?.right));
}

function setViewportVariables(webApp: TelegramWebApp) {
  const root = document.documentElement;
  const stableHeight = webApp.viewportStableHeight ?? webApp.viewportHeight;
  if (stableHeight && Number.isFinite(stableHeight) && stableHeight > 0) {
    root.style.setProperty("--tg-viewport-stable-height", `${stableHeight}px`);
  }
}

export default function useTelegramWebApp() {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) {
      // Not inside Telegram Mini App — no action needed
      return;
    }

    // Signal that app is ready ASAP to hide Telegram's loading screen
    webApp.ready();
    webApp.expand();

    // Apply theme colors if API supports it
    webApp.setHeaderColor?.("bg_color");
    webApp.setBackgroundColor?.("bg_color");
    webApp.setBottomBarColor?.("bottom_bar_bg_color");

    setInsetVariables(webApp);
    setViewportVariables(webApp);

    // Request fullscreen — errors are caught so they don't break the app
    if (webApp.requestFullscreen && !webApp.isFullscreen) {
      try {
        webApp.requestFullscreen();
      } catch {
        // Not supported on this platform — ignore
      }
    }

    const onViewportChanged = () => {
      setViewportVariables(webApp);
    };
    const onSafeAreaChanged = () => {
      setInsetVariables(webApp);
    };

    webApp.onEvent("viewportChanged", onViewportChanged);
    webApp.onEvent("safeAreaChanged", onSafeAreaChanged);
    webApp.onEvent("contentSafeAreaChanged", onSafeAreaChanged);

    return () => {
      webApp.offEvent("viewportChanged", onViewportChanged);
      webApp.offEvent("safeAreaChanged", onSafeAreaChanged);
      webApp.offEvent("contentSafeAreaChanged", onSafeAreaChanged);
    };
  }, []);
}
