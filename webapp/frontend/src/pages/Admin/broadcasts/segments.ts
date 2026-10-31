/**
 * The targeting grammar from CONTRACT_P12 §m008, kept as one string:
 * `all | pro | free | test_admins | lang:<uz|ru|en> | region:<soato> |
 * active_days:<n>` (`SEGMENT_RE` in `src/functions/broadcast_worker.py`).
 *
 * The UI splits it into a kind + a value so the form can show a second
 * control, then joins it back before the request.
 */
import type { TranslationKey } from "../../../i18n";

export const SEGMENT_KINDS = [
  "all",
  "pro",
  "free",
  "lang",
  "region",
  "active_days",
  "test_admins",
] as const;

export type SegmentKind = (typeof SEGMENT_KINDS)[number];

/** Kinds that need a second value (the `<prefix>:<value>` forms). */
export const PARAMETRIC_KINDS: SegmentKind[] = ["lang", "region", "active_days"];

export const SEGMENT_LABEL_KEY: Record<SegmentKind, TranslationKey> = {
  all: "adminBroadcasts.target.all",
  pro: "adminBroadcasts.target.pro",
  free: "adminBroadcasts.target.free",
  lang: "adminBroadcasts.target.lang",
  region: "adminBroadcasts.target.region",
  active_days: "adminBroadcasts.target.active_days",
  test_admins: "adminBroadcasts.target.test_admins",
};

export function buildSegment(kind: SegmentKind, value: string): string {
  if (!PARAMETRIC_KINDS.includes(kind)) return kind;
  return `${kind}:${value.trim()}`;
}

export function parseSegment(segment: string): { kind: SegmentKind; value: string } {
  const raw = (segment || "all").trim();
  const [prefix, ...rest] = raw.split(":");
  const kind = SEGMENT_KINDS.find((k) => k === prefix) ?? "all";
  return { kind, value: rest.join(":") };
}

/** `SEGMENT_RE` on the client: an invalid segment is refused before the round trip. */
export function isValidSegment(segment: string): boolean {
  return /^(all|pro|free|test_admins|lang:(uz|ru|en)|region:[A-Za-z0-9_-]{1,32}|active_days:\d{1,4})$/.test(
    segment,
  );
}
