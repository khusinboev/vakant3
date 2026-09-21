import parseApiError from "../../../lib/parseApiError";
import type { TranslationKey, TranslationVars } from "../../../i18n";

export type ChannelFormMessage = {
  key: TranslationKey;
  vars?: TranslationVars;
};

export type AddChannelFailure = {
  message: ChannelFormMessage;
  /** `CHANNEL_INVALID{reason: "invite_link_requires_chat_id"}` — reveal the chat-id field. */
  needsChatId: boolean;
};

/** `parse_channel_link` (src/functions/functions.py) + the router's own checks. */
const REASON_KEY: Record<string, TranslationKey> = {
  empty: "adminChannels.add.error.empty",
  bad_format: "adminChannels.add.error.badFormat",
  invite_link_requires_chat_id: "adminChannels.add.error.needsChatId",
  chat_not_found: "adminChannels.add.error.notFound",
};

/**
 * Turns a failed `POST /admin/channels` into one inline, translated line.
 * CONTRACT_P12 §m006 error codes: CHANNEL_INVALID{reason}, CHANNEL_BOT_NOT_ADMIN,
 * CHANNEL_EXISTS; anything else (network, UPSTREAM_ERROR, rate limit) falls
 * back to a generic retry message.
 */
export function describeAddChannelError(error: unknown): AddChannelFailure {
  const parsed = parseApiError(error);

  if (parsed.code === "CHANNEL_INVALID") {
    const reason = String(parsed.params.reason ?? "");
    return {
      message: { key: REASON_KEY[reason] ?? "adminChannels.add.error.badFormat" },
      needsChatId: reason === "invite_link_requires_chat_id",
    };
  }

  if (parsed.code === "CHANNEL_BOT_NOT_ADMIN") {
    const title = parsed.params.title ? String(parsed.params.title) : "";
    return {
      message: {
        key: title ? "adminChannels.add.error.notAdminNamed" : "adminChannels.add.error.notAdmin",
        vars: title ? { title } : undefined,
      },
      needsChatId: false,
    };
  }

  if (parsed.code === "CHANNEL_EXISTS") {
    return {
      message: { key: "adminChannels.add.error.exists", vars: { id: String(parsed.params.id ?? "") } },
      needsChatId: false,
    };
  }

  if (parsed.code === "UPSTREAM_ERROR") {
    return { message: { key: "adminChannels.add.error.upstream" }, needsChatId: false };
  }

  return { message: { key: "adminChannels.add.error.generic" }, needsChatId: false };
}
