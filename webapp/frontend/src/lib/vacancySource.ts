/**
 * The original posting URL when it is a plain https link (anything else is never opened).
 * It is only the target of the neutral "Apply" button: the source site is never named in the UI.
 */
export function originalUrl(value: unknown): string | null {
  return typeof value === "string" && /^https:\/\/[^\s]+$/.test(value) ? value : null;
}
