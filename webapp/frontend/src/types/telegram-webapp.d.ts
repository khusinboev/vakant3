declare global {
  interface TelegramWebApp {
    /** Raw initData string — send to backend for HMAC verification */
    initData: string;
    version: string;
    platform: string;
    colorScheme: "light" | "dark";
    isExpanded: boolean;
    isFullscreen: boolean;
    isActive: boolean;
    viewportHeight: number;
    viewportStableHeight: number;
    safeAreaInset: { top: number; bottom: number; left: number; right: number };
    contentSafeAreaInset: { top: number; bottom: number; left: number; right: number };
    ready: () => void;
    expand: () => void;
    close: () => void;
    setHeaderColor?: (color: string) => void;
    setBackgroundColor?: (color: string) => void;
    setBottomBarColor?: (color: string) => void;
    requestFullscreen?: () => void;
    exitFullscreen?: () => void;
    lockOrientation?: () => void;
    unlockOrientation?: () => void;
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
