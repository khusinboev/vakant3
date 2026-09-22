/** adminChannels namespace — owned by the corresponding admin page agent. uz is the source. */
const adminChannels = {
  "adminChannels.title": "Kanallar",

  // ── Gate explainer (closed Accordion item at the bottom) ─────────────────
  "adminChannels.info.title": "Kirish shartlari qanday ishlaydi",
  "adminChannels.info.step.start": "Bot start",
  "adminChannels.info.step.subscribe": "Obuna",
  "adminChannels.info.step.referral": "Referral",
  "adminChannels.info.description": "Referral shartini yoqish va talab qilinadigan son",
  "adminChannels.info.settingsLink": "Sozlamalar sahifasida sozlanadi",

  // ── Add sheet ────────────────────────────────────────────────────────────
  "adminChannels.add.title": "Kanal qo'shish",
  "adminChannels.add.linkLabel": "Kanal havolasi",
  "adminChannels.add.linkHint": "@nomi, t.me/nomi, t.me/+taklif yoki -100 ID",
  "adminChannels.add.linkPlaceholder": "@mening_kanalim",
  "adminChannels.add.chatIdLabel": "Chat ID",
  "adminChannels.add.chatIdHint": "Yopiq taklif havolalari uchun raqamli ID kerak",
  "adminChannels.add.checking": "Tekshirilmoqda...",
  "adminChannels.add.submit": "Qo'shish",
  "adminChannels.add.success.admin": "Bot ushbu kanalda admin ✓",
  "adminChannels.add.error.empty": "Havola kiritilmadi.",
  "adminChannels.add.error.badFormat": "Havola formati noto'g'ri. @nomi, t.me/nomi yoki -100 ID kiriting.",
  "adminChannels.add.error.needsChatId": "Bu yopiq taklif havolasi — pastda chat ID'ni ham kiriting.",
  "adminChannels.add.error.notFound": "Bunday kanal topilmadi.",
  "adminChannels.add.error.notAdmin": "Bot bu kanalda admin emas. Botni kanalga admin qilib qo'shing.",
  "adminChannels.add.error.notAdminNamed":
    "Bot \"{title}\" kanalida admin emas. Botni admin qilib qo'shing.",
  "adminChannels.add.error.exists": "Bu kanal allaqachon qo'shilgan ({id}).",
  "adminChannels.add.error.upstream": "Telegram bilan bog'lanib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.",
  "adminChannels.add.error.generic": "Kanalni qo'shib bo'lmadi. Qayta urinib ko'ring.",

  // ── List row ─────────────────────────────────────────────────────────────
  "adminChannels.status.never": "Hali tekshirilmagan",
  "adminChannels.chip.ok": "OK",
  "adminChannels.chip.fail": "Xato",
  "adminChannels.chip.unknown": "—",
  "adminChannels.toggle.enable": "{name} — yoqish",
  "adminChannels.toggle.disable": "{name} — o'chirish",
  "adminChannels.action.check": "{name} — hozir tekshirish",
  "adminChannels.action.delete": "{name} — o'chirish",
  "adminChannels.check.ok": "Kanal holati yaxshi — bot admin.",
  "adminChannels.check.failed": "Muammo topildi. Kanal ro'yxatidagi holatni ko'ring.",
  "adminChannels.empty": "Hali kanal qo'shilmagan.",

  // ── Delete ───────────────────────────────────────────────────────────────
  "adminChannels.delete.title": "Kanalni o'chirasizmi?",
  "adminChannels.delete.description":
    "\"{name}\" kirish shartidan olib tashlanadi. Bu amalni bekor qilib bo'lmaydi.",
  "adminChannels.delete.success": "Kanal o'chirildi.",
};
export type AdminChannelsDict = typeof adminChannels;
export default adminChannels;
