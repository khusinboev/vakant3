declare global {
  interface TelegramWebApp {
    /** Raw initData string — send to backend for HMAC verification */
    initData: string;
    version: string;
    platform: string;
    colorScheme: "light" | "dark";
    isExpanded: boolean;
    /** Bot API 8.0+ */
    isFullscreen: boolean;
    /** Bot API 8.0+ */
    isActive: boolean;
    viewportHeight: number;
    viewportStableHeight: number;
    safeAreaInset: { top: number; bottom: number; left: number; right: number };
    contentSafeAreaInset: { top: number; bottom: number; left: number; right: number };
    /** Returns true if the user's Telegram app supports a Bot API version >= the given string */
    isVersionAtLeast: (version: string) => boolean;
    ready: () => void;
    expand: () => void;
    close: () => void;
    setHeaderColor?: (color: string) => void;
    setBackgroundColor?: (color: string) => void;
    setBottomBarColor?: (color: string) => void;
    /** Bot API 8.0+ */
    requestFullscreen?: () => void;
    /** Bot API 8.0+ */
    exitFullscreen?: () => void;
    /** Bot API 8.0+ */
    lockOrientation?: () => void;
    /** Bot API 8.0+ */
    unlockOrientation?: () => void;
    /** Bot API 7.7+ — disable vertical swipe-to-close */
    disableVerticalSwipes?: () => void;
    /** Bot API 7.7+ — re-enable vertical swipe-to-close */
    enableVerticalSwipes?: () => void;
    onEvent: (eventType: string, callback: () => void) => void;
    offEvent: (eventType: string, callback: () => void) => void;
    sendData: (data: string) => void;
    showPopup: (
      params: { title?: string; message: string; buttons?: { id?: string; type?: string; text?: string }[] },
      callback?: (buttonId: string) => void,
    ) => void;
    showAlert: (message: string, callback?: () => void) => void;
    showConfirm: (message: string, callback?: (ok: boolean) => void) => void;
  }

  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export {};
