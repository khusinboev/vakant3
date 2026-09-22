import { useEffect, useMemo, useRef } from "react";

import { isTelegramWebApp } from "../../../hooks/useTelegramAuth";
import { useT } from "../../../i18n/useT";
import type { TranslationKey } from "../../../i18n";

export type HapticKind = "success" | "error" | "warning" | "light";

/**
 * Telegram's own feedback, silently ignored everywhere else.
 * Called after a confirmed mutation (`success`) or a failed one (`error`).
 */
export function haptic(kind: HapticKind): void {
  const feedback = window.Telegram?.WebApp?.HapticFeedback;
  if (!feedback) return;
  try {
    if (kind === "light") feedback.impactOccurred("light");
    else feedback.notificationOccurred(kind);
  } catch {
    // An older Telegram client: feedback is a nicety, never a requirement.
  }
}

/** `true` when this client can render a native MainButton. */
export function hasNativeMainButton(): boolean {
  return isTelegramWebApp() && Boolean(window.Telegram?.WebApp?.MainButton);
}

export type MainButtonOptions = {
  /** Already translated label. Use `textKey` to have the hook translate. */
  text?: string;
  textKey?: TranslationKey;
  onClick: () => void;
  enabled?: boolean;
  loading?: boolean;
  visible?: boolean;
};

export type MainButtonApi = {
  /** `false` -> the caller must render an in-page `ActionBar` instead. */
  native: boolean;
};

/**
 * The screen's single primary action, delegated to `WebApp.MainButton`.
 *
 *   const { native } = useMainButton({ textKey: "adminBroadcasts.queue", onClick: queue, loading });
 *   {!native && <ActionBar primary={{ labelKey: "adminBroadcasts.queue", onClick: queue }} />}
 *
 * `AdminShell` does this automatically for the header's `primary` action, so a
 * page normally only declares `useAdminHeader({ primary })`.
 */
export function useMainButton(options: MainButtonOptions): MainButtonApi {
  const t = useT();
  const { text, textKey, onClick, enabled = true, loading = false, visible = true } = options;
  const label = textKey ? t(textKey) : (text ?? "");

  const handlerRef = useRef(onClick);
  handlerRef.current = onClick;

  const native = hasNativeMainButton();

  useEffect(() => {
    if (!native) return;
    const button = window.Telegram?.WebApp?.MainButton;
    if (!button) return;

    const handleClick = () => handlerRef.current();
    button.onClick(handleClick);
    return () => {
      button.offClick(handleClick);
      button.hideProgress();
      button.hide();
    };
  }, [native]);

  useEffect(() => {
    if (!native) return;
    const button = window.Telegram?.WebApp?.MainButton;
    if (!button) return;

    if (!visible) {
      button.hideProgress();
      button.hide();
      return;
    }

    if (label) button.setText(label);
    if (loading) button.showProgress(true);
    else button.hideProgress();
    if (enabled && !loading) button.enable();
    else button.disable();
    button.show();
  }, [native, visible, label, enabled, loading]);

  return useMemo(() => ({ native }), [native]);
}

export default useMainButton;
