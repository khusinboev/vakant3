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
