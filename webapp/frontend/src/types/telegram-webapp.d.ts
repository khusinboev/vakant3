declare global {
  interface TelegramWebAppUser {
    id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    language_code?: string;
    photo_url?: string;
    is_premium?: boolean;
    allows_write_to_pm?: boolean;
    added_to_attachment_menu?: boolean;
    is_bot?: boolean;
  }

  interface TelegramWebAppInitDataUnsafe {
    query_id?: string;
    user?: TelegramWebAppUser;
    auth_date?: string;
    hash?: string;
    start_param?: string;
    chat_type?: string;
    chat_instance?: string;
    signature?: string;
  }

  interface TelegramBackButton {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  }

  interface TelegramWebApp {
    initData: string;
    initDataUnsafe?: TelegramWebAppInitDataUnsafe;
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
    isVersionAtLeast: (version: string) => boolean;
    BackButton: TelegramBackButton;
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
    disableVerticalSwipes?: () => void;
    enableVerticalSwipes?: () => void;
    onEvent: (eventType: string, callback: () => void) => void;
    offEvent: (eventType: string, callback: () => void) => void;
    sendData: (data: string) => void;
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
