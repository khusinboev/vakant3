import type { AdminChannelsDict } from "../uz/adminChannels";

const adminChannels: Record<keyof AdminChannelsDict, string> = {
  "adminChannels.title": "Channels",
  "adminChannels.subtitle": "Channels a user must subscribe to before the app lets them in.",

  "adminChannels.info.title": "How the entry gate works",
  "adminChannels.info.step.start": "Bot start",
  "adminChannels.info.step.subscribe": "Subscription",
  "adminChannels.info.step.referral": "Referral",
  "adminChannels.info.description": "The referral toggle and required count are",
  "adminChannels.info.settingsLink": "configured on the Settings page",

  "adminChannels.add.title": "Add a channel",
  "adminChannels.add.linkLabel": "Channel link",
  "adminChannels.add.linkHint": "@name, t.me/name, t.me/+invite or a -100 chat id",
  "adminChannels.add.linkPlaceholder": "@my_channel",
  "adminChannels.add.chatIdLabel": "Chat ID",
  "adminChannels.add.chatIdHint": "Required for private invite links — Telegram can't resolve them without it",
  "adminChannels.add.checking": "Checking...",
  "adminChannels.add.submit": "Add",
  "adminChannels.add.success.admin": "The bot is an admin here ✓",
  "adminChannels.add.error.empty": "Enter a link first.",
  "adminChannels.add.error.badFormat": "That doesn't look like a valid link. Try @name, t.me/name or a -100 chat id.",
  "adminChannels.add.error.needsChatId": "That's a private invite link — enter the numeric chat id below too.",
  "adminChannels.add.error.notFound": "Telegram couldn't find that channel.",
  "adminChannels.add.error.notAdmin": "The bot isn't an admin there. Add the bot as an admin in the channel.",
  "adminChannels.add.error.notAdminNamed":
    "The bot isn't an admin in \"{title}\". Add the bot as an admin there.",
  "adminChannels.add.error.exists": "This channel is already on the list ({id}).",
  "adminChannels.add.error.upstream": "Couldn't reach Telegram. Try again in a moment.",
  "adminChannels.add.error.generic": "Couldn't add the channel. Try again.",

  "adminChannels.table.caption": "Required subscription channels",
  "adminChannels.column.channel": "Channel",
  "adminChannels.column.status": "Status",
  "adminChannels.column.enabled": "Enabled",
  "adminChannels.column.actions": "Actions",
  "adminChannels.status.never": "Never checked",
  "adminChannels.status.ok": "OK — {time}",
  "adminChannels.status.failed": "Issue found — {time}",
  "adminChannels.status.enabled": "Enabled",
  "adminChannels.status.disabled": "Disabled",
  "adminChannels.action.check": "Check {name} now",
  "adminChannels.action.delete": "Delete {name}",
  "adminChannels.check.ok": "All good — the bot is an admin.",
  "adminChannels.check.failed": "Found an issue — check the status in the list.",
  "adminChannels.empty": "No channels added yet.",

  "adminChannels.delete.title": "Delete this channel?",
  "adminChannels.delete.description": "\"{name}\" will be removed from the entry gate. This can't be undone.",
  "adminChannels.delete.success": "Channel deleted.",
};
export default adminChannels;
