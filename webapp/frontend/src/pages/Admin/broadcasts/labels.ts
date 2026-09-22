/**
 * The small shared vocabulary of the broadcasts page: kind + status labels,
 * their kit tones, the status sets the page branches on, and the one dense
 * input class the composer's fields use (32px, 13px — spec §1.4).
 */
import type { BroadcastKind, BroadcastStatus } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import type { Tone } from "../ui";

/** Kind -> label key. A map, not a template string, so `t()` stays type-checked. */
export const KIND_LABEL_KEY: Record<BroadcastKind, TranslationKey> = {
  text: "adminBroadcasts.kind.text",
  photo: "adminBroadcasts.kind.photo",
  video: "adminBroadcasts.kind.video",
  document: "adminBroadcasts.kind.document",
  forward: "adminBroadcasts.kind.forward",
};

/** `forward` broadcasts come from the bot's forward flow, never the composer. */
export const COMPOSABLE_KINDS: BroadcastKind[] = ["text", "photo", "video", "document"];

export const STATUS_LABEL_KEY: Record<BroadcastStatus, TranslationKey> = {
  draft: "adminBroadcasts.status.draft",
  queued: "adminBroadcasts.status.queued",
  running: "adminBroadcasts.status.running",
  paused: "adminBroadcasts.status.paused",
  cancelled: "adminBroadcasts.status.cancelled",
  done: "adminBroadcasts.status.done",
  failed: "adminBroadcasts.status.failed",
};

/**
 * `statusTone()` in the kit covers six of the seven; `paused` is the one the
 * shared map reads as neutral, and a paused job is a warning here.
 */
const STATUS_TONE: Record<BroadcastStatus, Tone> = {
  draft: "neutral",
  queued: "warning",
  running: "info",
  paused: "warning",
  cancelled: "neutral",
  done: "success",
  failed: "danger",
};

export function statusLabelKey(status: string): TranslationKey {
  return STATUS_LABEL_KEY[status as BroadcastStatus] ?? STATUS_LABEL_KEY.draft;
}

export function statusToneOf(status: string): Tone {
  return STATUS_TONE[status as BroadcastStatus] ?? "neutral";
}

/** Statuses the bot worker is still touching — they are what makes the page poll. */
export const ACTIVE_STATUSES = new Set<string>(["queued", "running"]);

/** Statuses `/cancel` accepts (`webapp/routers/admin_broadcasts.py`). */
export const CANCELLABLE = new Set<string>(["draft", "queued", "running", "paused"]);

/** 32px input/select, 13px text — the app-wide `INPUT_CLS` is 44px and too tall here. */
export const FIELD_CLS =
  "h-8 w-full min-w-0 rounded-xl border border-border bg-surface px-2.5 text-[13px] text-text " +
  "placeholder:text-muted/70 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40";

/** First non-empty line of a Telegram-HTML message, for a list row title. */
export function firstLine(html: string | null | undefined): string {
  if (!html) return "";
  const plain = html
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
  const line = plain.split("\n").map((part) => part.trim()).find(Boolean) ?? "";
  return line.length > 120 ? `${line.slice(0, 120)}…` : line;
}
