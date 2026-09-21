import type { BroadcastKind } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";

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
