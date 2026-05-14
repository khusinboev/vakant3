/**
 * Returns true when the page is running inside Telegram WebApp.
 */
export function isTelegramWebApp(): boolean {
  return Boolean(
    typeof window !== "undefined" &&
      (window as Window & { Telegram?: { WebApp?: unknown } }).Telegram?.WebApp
  );
}

/**
 * Placeholder — auto-auth removed. Kept as named export for App.tsx import.
 */
export default function useTelegramAuth() {}
