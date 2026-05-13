declare global {
  interface TelegramWebApp {
    ready: () => void;
    expand: () => void;
    setHeaderColor?: (color: string) => void;
    setBackgroundColor?: (color: string) => void;
    setBottomBarColor?: (color: string) => void;
    requestFullscreen?: () => void;
    isFullscreen?: boolean;
    viewportStableHeight?: number;
    viewportHeight?: number;
    safeAreaInset?: { top: number; bottom: number; left: number; right: number };
    contentSafeAreaInset?: { top: number; bottom: number; left: number; right: number };
    onEvent: (eventType: string, callback: () => void) => void;
    offEvent: (eventType: string, callback: () => void) => void;
  }

  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

export {};
