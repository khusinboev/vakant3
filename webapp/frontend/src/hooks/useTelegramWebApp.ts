import { useEffect } from "react";

function px(value: number | undefined): string {
  return `${Math.max(0, Number(value ?? 0))}px`;
}

/**
 * Write the OFFICIAL Telegram SDK CSS variable names
 * (--tg-safe-area-inset-*, --tg-content-safe-area-inset-*).
 * The SDK auto-injects these too, but writing them in JS ensures they are
 * available on the very first render frame and stay in sync on every event.
 * index.css bridges them to our short alias names used in components.
 */
function setInsetVariables(webApp: TelegramWebApp) {
  const root = document.documentElement;
  const safe = webApp.safeAreaInset;
  const contentSafe = webApp.contentSafeAreaInset;

  // System safe area (notch, home indicator, navigation bars)
  root.style.setProperty("--tg-safe-area-inset-top",    px(safe?.top));
  root.style.setProperty("--tg-safe-area-inset-bottom", px(safe?.bottom));
  root.style.setProperty("--tg-safe-area-inset-left",   px(safe?.left));
  root.style.setProperty("--tg-safe-area-inset-right",  px(safe?.right));

  // Content safe area (avoids Telegram's own UI: header, bottom bar)
  root.style.setProperty("--tg-content-safe-area-inset-top",    px(contentSafe?.top));
  root.style.setProperty("--tg-content-safe-area-inset-bottom", px(contentSafe?.bottom));
  root.style.setProperty("--tg-content-safe-area-inset-left",   px(contentSafe?.left));
  root.style.setProperty("--tg-content-safe-area-inset-right",  px(contentSafe?.right));
}

function setViewportVariables(webApp: TelegramWebApp) {
  const root = document.documentElement;
  const stableHeight = webApp.viewportStableHeight ?? webApp.viewportHeight;
  if (stableHeight && Number.isFinite(stableHeight) && stableHeight > 0) {
    root.style.setProperty("--tg-viewport-stable-height", `${stableHeight}px`);
  }
  // Track the CURRENT (keyboard-aware) viewport height so layouts that need
  // to respond to the on-screen keyboard can bind to --tg-viewport-height.
  const currentHeight = webApp.viewportHeight;
  if (currentHeight && Number.isFinite(currentHeight) && currentHeight > 0) {
    root.style.setProperty("--tg-viewport-height", `${currentHeight}px`);
  }
}

/**
 * In fullscreen the Telegram header becomes transparent.
 * Setting bg_color gives the OS status bar the correct contrast color.
 */
function applyColors(webApp: TelegramWebApp) {
  webApp.setHeaderColor?.("bg_color");
  webApp.setBackgroundColor?.("bg_color");
  webApp.setBottomBarColor?.("bottom_bar_bg_color");
}

export default function useTelegramWebApp() {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    // Signal ready ASAP → hides Telegram's loading placeholder
    webApp.ready();
    webApp.expand();

    applyColors(webApp);
    setInsetVariables(webApp);
    setViewportVariables(webApp);

    // Bot API 7.7+ — disable vertical swipe-to-close while content is scrollable
    webApp.disableVerticalSwipes?.();

    // Bot API 8.0+ — request fullscreen
    if (webApp.isVersionAtLeast?.("8.0") && !webApp.isFullscreen) {
      webApp.requestFullscreen?.();
    }

    // ── Event handlers ──────────────────────────────────────────────────────

    const onViewportChanged = () => setViewportVariables(webApp);

    const onSafeAreaChanged = () => setInsetVariables(webApp);

    // Fires when fullscreen is entered or exited (Bot API 8.0+).
    // Re-apply header color so status bar text contrast stays correct.
    const onFullscreenChanged = () => {
      document.documentElement.dataset.fullscreen = webApp.isFullscreen ? "1" : "0";
      applyColors(webApp);
    };

    // Fires when requestFullscreen() fails (unsupported platform, etc.) — ignore.
    const onFullscreenFailed = () => { /* noop — platforms without fullscreen support */ };

    // Fires when app is restored from minimised state (Bot API 8.0+).
    // Re-sync layout vars in case they changed while the app was inactive.
    const onActivated = () => {
      setInsetVariables(webApp);
      setViewportVariables(webApp);
      applyColors(webApp);
    };

    webApp.onEvent("viewportChanged",        onViewportChanged);
    webApp.onEvent("safeAreaChanged",        onSafeAreaChanged);
    webApp.onEvent("contentSafeAreaChanged", onSafeAreaChanged);
    webApp.onEvent("fullscreenChanged",      onFullscreenChanged);
    webApp.onEvent("fullscreenFailed",       onFullscreenFailed);
    webApp.onEvent("activated",              onActivated);

    // Visual Viewport API: updates --tg-viewport-height on every keyboard
    // animation frame — works in Telegram WebView and regular browsers alike.
    const onVisualResize = () => {
      const h = window.visualViewport?.height;
      if (h && h > 0) {
        document.documentElement.style.setProperty("--tg-viewport-height", `${Math.round(h)}px`);
      }
    };
    window.visualViewport?.addEventListener("resize", onVisualResize);
    // Initialise immediately in case the hook mounts after the keyboard is already open.
    onVisualResize();

    return () => {
      webApp.offEvent("viewportChanged",        onViewportChanged);
      webApp.offEvent("safeAreaChanged",        onSafeAreaChanged);
      webApp.offEvent("contentSafeAreaChanged", onSafeAreaChanged);
      webApp.offEvent("fullscreenChanged",      onFullscreenChanged);
      webApp.offEvent("fullscreenFailed",       onFullscreenFailed);
      webApp.offEvent("activated",              onActivated);
      window.visualViewport?.removeEventListener("resize", onVisualResize);
    };
  }, []);
}
