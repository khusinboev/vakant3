/** Display names of the vacancy store's sources (brand names, not translated). */
const SOURCE_LABELS: Record<string, string> = { osonish: "osonish.uz", hh: "hh.uz" };

/** "hh.uz" / "osonish.uz" for a source, preferring the label the API sent. */
export function sourceLabel(source?: string | null, label?: string | null): string | null {
  if (label) return label;
  if (!source) return null;
  return SOURCE_LABELS[source] ?? source;
}

/** The original posting URL when it is a plain https link (anything else is never opened). */
export function originalUrl(value: unknown): string | null {
  return typeof value === "string" && /^https:\/\/[^\s]+$/.test(value) ? value : null;
}
