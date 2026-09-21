/**
 * Uzbek is the SOURCE language. Every other language is typed against these
 * keys (`Record<keyof CommonDict, string>`), so a missing/extra key in ru or en
 * is a compile error.
 *
 * Key convention: `<area>.<name>`, flat, dot separated, lowerCamelCase names.
 * Interpolation placeholders are `{name}`.
 */
const common = {
  // ── Generic ────────────────────────────────────────────────────────────────
  "common.loading": "Yuklanmoqda...",
  "common.retry": "Qayta urinish",
  "common.close": "Yopish",
  "common.cancel": "Bekor qilish",
  "common.apply": "Qo'llash",
  "common.save": "Saqlash",
  "common.saving": "Saqlanmoqda...",
  "common.copy": "Nusxa",
  "common.share": "Ulashish",
  "common.shareShort": "Ulash",
  "common.details": "Batafsil",
  "common.delete": "O'chirish",
  "common.statistics": "Statistika",
  "common.all": "Barchasi",
  "common.optional": "ixtiyoriy",
  "common.sum": "so'm",
  "common.notSpecified": "Ko'rsatilmagan",
  "common.itemsCount": "{n} ta",
  "common.empty": "Ma'lumot yo'q",

  // ── App shell / errors ─────────────────────────────────────────────────────
  "app.name": "Bandlik.uz",
  "app.errorTitle": "Nimadir noto'g'ri ketdi",
  "app.errorBody": "Sahifani yuklashda xatolik yuz berdi. Qayta urinib ko'ring.",
  "app.reload": "Sahifani yangilash",
  "app.referralLockTitle": "Referral sharti yoqilgan",
  "app.referralLockBody": "Ilovadan foydalanish uchun avval referral shartini bajaring.",
  "app.referralLockStatus": "Holat: {current}/{required}",
  "app.referralLockShare": "Referral havolani ulashish",

  // ── Kirish nazorati (entry gate) ───────────────────────────────────────────
  "gate.botStartTitle": "Avval botni ishga tushiring",
  "gate.botStartBody":
    "Ilovadan foydalanish uchun botga o'ting va /start tugmasini bosing, so'ng bu sahifaga qayting.",
  "gate.botStartAction": "Botni ochish",
  "gate.subscribeTitle": "Kanallarga obuna bo'ling",
  "gate.subscribeBody":
    "Ilovadan foydalanish uchun quyidagi kanallarga obuna bo'ling va \"Qayta tekshirish\" tugmasini bosing.",
  "gate.channelFallback": "Kanal",
  "gate.checkAgain": "Qayta tekshirish",
  "gate.checking": "Tekshirilmoqda...",
  "gate.stillLocked": "Hali hammasi bajarilmadi. Iltimos, qaytadan urinib ko'ring.",
  "gate.bannedTitle": "Hisobingiz bloklangan",
  "gate.bannedBody": "Ilovadan foydalanish cheklangan. Savollar bo'lsa, administratorga murojaat qiling.",

  // ── Bottom navigation ──────────────────────────────────────────────────────
  "nav.home": "Bosh sahifa",
  "nav.profile": "Profil",
  "nav.hub": "Markaz",
  "nav.admin": "Admin",

  // ── Login prompt ───────────────────────────────────────────────────────────
  "login.title": "Kirish kerak",
  "login.body": "Bu funksiyadan foydalanish uchun botda hisobingiz bo'lishi kerak.",
  "login.toBot": "Botga qaytish",

  // ── Home / job list ────────────────────────────────────────────────────────
  "home.errorLoad": "Natijalar yuklanmadi. Qayta urinib ko'ring.",
  "home.count": "{n} ta vakansiya",
  "home.page": "{page} / {total}",
  "home.empty": "Natija topilmadi. Boshqa kalit so'z yoki filtr sinab ko'ring.",
  "home.allShown": "Barcha natijalar ko'rsatildi",
  "home.saveLimitTitle": "Saqlash limiti ({current}/{limit})",
  "home.saveLimitBody":
    "Bepul tarifda {limit} tagacha ish saqlanadi. Cheksiz saqlash uchun Pro tarifga o'ting.",
  "home.goPro": "Pro tarifga o'tish",

  // ── Search filters ─────────────────────────────────────────────────────────
  "filters.searchPlaceholder": "Kasb, lavozim nomi",
  "filters.open": "Filtrlarni ochish",
  "filters.sectors": "Sohalar",
  "filters.allFilters": "Barcha filterlar",
  "filters.sort": "Saralash",
  "filters.sortNew": "Yangi",
  "filters.sortSalary": "Yuqori maosh",
  "filters.sortOld": "Eski",
  "filters.allRegions": "Barcha viloyatlar",
  "filters.allDistricts": "Barcha tumanlar",
  "filters.salary": "Maosh",
  "filters.salaryFrom": "{n} mln +",
  "filters.clear": "Qo'shimcha filterlarni tozalash",
  "filters.sector.all": "Barchasi",
  "filters.sector.industry": "Sanoat",
  "filters.sector.services": "Xizmatlar",
  "filters.sector.education": "Ta'lim",
  "filters.sector.health": "Sog'liq",
  "filters.sector.construction": "Qurilish",
  "filters.sector.it": "IT",
  "filters.sector.trade": "Savdo",

  // ── Saves ──────────────────────────────────────────────────────────────────
  "saves.title": "Saqlangan ishlar",
  "saves.tgOnly": "Bu bo'lim faqat Telegram ichidan ochilganda ishlaydi.",
  "saves.login": "Kirish",
  "saves.error": "Saqlangan ishlarni yuklab bo'lmadi.",
  "saves.empty": "Saqlangan ishlar yo'q. Ishlarni saqlash uchun yurakcha tugmasini bosing.",

  // ── Hub ────────────────────────────────────────────────────────────────────
  "hub.title": "Markaz",
  "hub.subtitle": "Resume bo'limiga kirib ma'lumotlaringizni to'ldiring.",
  "hub.resume": "Resume",
  "hub.resumeDesc": "Oddiy formani to'ldirib saqlang yoki Telegramga yuboring.",
  "hub.resumeCta": "Resume bo'limiga kirish",
  "hub.laws": "Qonunchilik",
  "hub.lawsDesc": "O'zbekiston Mehnat Kodeksi bo'yicha huquqlaringizni biling.",
  "hub.lawsCta": "Maqolalarni ko'rish",

  // ── Landing (outside Telegram) ─────────────────────────────────────────────
  "landing.badge": "Ish qidirish platformasi",
  "landing.body":
    "Eng dolzarb bo'sh ish o'rinlarini Telegram bot orqali tez va qulay toping. Barcha imkoniyatlar bot ichida bir joyda.",
  "landing.cta": "Telegram botga o'tish",

  // ── Referral ───────────────────────────────────────────────────────────────
  "referral.perInvite": "Har bir taklif uchun",
  "referral.rewardAmount": "+{amount} so'm",
  "referral.autoCredit": "Hisobingizga avtomatik tushadi",
  "referral.yourLink": "Sizning havolangiz",
  "referral.invitedWithCount": "Taklif qilinganlar: {n} ta",
  "referral.income": "Referral daromad",
  "referral.invited": "Taklif qilinganlar",
  "referral.totalEarned": "Jami daromad (so'm)",
  "referral.emptyList": "Hali hech kim qo'shilmagan. Havolangizni ulashing.",
  "referral.shareText":
    "Bandlik.uz — Telegram orqali ish topishning eng qulay yo'li! Qo'shiling:",
  "referral.anonymous": "Foydalanuvchi",
  "referral.copied": "Havola nusxalandi",
  "referral.loadError": "Referral ma'lumotlarini yuklab bo'lmadi.",

  // ── Wallet ─────────────────────────────────────────────────────────────────
  "wallet.balance": "Hamyon balansi",
  "wallet.proActive": "PRO tarif faol",
  "wallet.freePlan": "Boshlang'ich tarif",
  "wallet.notFound": "Hamyon ma'lumotlari topilmadi. Telegram orqali kiring.",
  "wallet.proTitle": "Pro tarif",
  "wallet.proDesc": "Pro tarif bilan yuqori maoshli ishlar uchun kontakt raqamlar ochiladi.",
  "wallet.price": "Narxi",
  "wallet.balanceLabel": "Balans",
  "wallet.activate": "Pro tarifni aktivlashtirish",
  "wallet.activating": "Faollashtirilmoqda...",
  "wallet.activated": "Pro tarif faollashtirildi",
  "wallet.needMore": "Pro uchun yana {amount} so'm kerak.",
  "wallet.referralWayTitle": "Eng oson usul: referral orqali",
  "wallet.referralWayBody":
    "Do'stlaringizni taklif qiling. Har bir do'stingiz botga qo'shilganda hisobingizga {amount} so'm tushadi.",
  "wallet.autoPro": "{amount} so'm to'plansa, Pro tarif avtomatik yoqiladi",
  "wallet.adminTitle": "Admin orqali pul qo'shish",
  "wallet.adminBody":
    "Agar Pro tarifni darhol olmoqchi bo'lsangiz, admindan hisobingizga {amount} so'm qo'shib berishini so'rashingiz mumkin.",
  "wallet.adminCta": "Admin bilan bog'lanish",
  "wallet.adminMessage":
    "Salom! Pro tarifga o'tish uchun hisobimga {amount} so'm qo'shib berish kerak.\n\nTelegram ID: {userId}\n\nRahmat!",
  "wallet.proActiveBody": "Barcha yuqori maoshli ish e'lonlari sizga ochiq.",
  "wallet.inviteTitle": "Do'stlaringizni taklif qiling",
  "wallet.inviteBody": "Har bir taklif qilgan do'stingiz uchun {amount} so'm olasiz.",
  "wallet.refStats": "Referral statistikasi",

  // ── Laws ───────────────────────────────────────────────────────────────────
  "laws.title": "Qonunchilik",
  "laws.subtitle": "O'zbekiston Mehnat Kodeksi asosidagi maqolalar",
  "laws.error": "Ma'lumotlarni yuklab bo'lmadi. Internet aloqasini tekshiring.",
  "laws.empty": "Bu bo'limda maqolalar yo'q.",
  "laws.readFull": "lex.uz'da to'liq o'qish",

  // ── Profile ────────────────────────────────────────────────────────────────
  "profile.title": "Profil",
  "profile.tgOnly": "Profil ma'lumotlari Telegram ichida ochilganda ko'rinadi.",
  "profile.userNotFound":
    "Telegram foydalanuvchi ma'lumotlari topilmadi. WebApp tugmasi orqali qayta ochib ko'ring.",
  "profile.tgUser": "Telegram foydalanuvchi",
  "profile.pro": "PRO",
  "profile.free": "Boshlang'ich",
  "profile.statSaved": "Saqlangan",
  "profile.statReferrals": "Referallar",
  "profile.statBalance": "Balans (so'm)",
  "profile.savedJobs": "Saqlangan ishlar",
  "profile.wallet": "Hamyon",
  "profile.inviteTitle": "Do'stlarni taklif qiling",
  "profile.inviteBody": "Har bir taklif qilgan do'stingiz uchun hisobingizga pul tushadi.",
  "profile.gateTitle": "Kirish sharti",
  "profile.gateReferrals": "Referallar",
  "profile.notifications": "Bildirishnomalar",
  "profile.notifToggleAria": "Bildirishnomalarni yoqish yoki o'chirish",
  "profile.notifOn": "Filtrlaringiz asosida yangi ishlar haqida kunlik xabar olasiz.",
  "profile.notifOffPro": "Yoqing — filtrlaringizga mos yangi ishlar haqida xabar olasiz.",
  "profile.notifOffFree": "Faqat Pro tarif uchun. Pro ga o'ting va bildirishnomalarni yoqing.",
  "profile.notifSettings": "Bildirishnoma sozlamalari",
  "profile.notifSettingsBody": "Qiziqishlaringizga mos ishlar haqida kunlik xabar olasiz.",
  "profile.region": "Hudud",
  "profile.sector": "Soha",
  "profile.minSalary": "Minimal maosh",
  "profile.minSalaryPlaceholder": "Masalan: 3 000 000",
  "profile.enableNotif": "Bildirishnomani yoqish",
  "profile.proNotifTitle": "Bildirishnomalar Pro tarif uchun",
  "profile.proNotifBody": "Kunlik ish tavsiyalarini olish uchun Pro tarifga o'ting.",

  // ── Settings card (language + theme) ───────────────────────────────────────
  "settings.title": "Sozlamalar",
  "settings.language": "Til",
  "settings.theme": "Mavzu",
  "settings.theme.telegram": "Telegram",
  "settings.theme.light": "Yorug'",
  "settings.theme.dark": "Qorong'i",
  "settings.theme.system": "Tizim",
  "settings.langSaved": "Til o'zgartirildi",

  // ── API error codes (see CONTRACT.md) ──────────────────────────────────────
  "error.AUTH_REQUIRED": "Avval tizimga kiring.",
  "error.INVALID_INIT_DATA": "Telegram ma'lumotlari yaroqsiz. Ilovani qayta oching.",
  "error.SESSION_EXPIRED": "Sessiya muddati tugadi. Ilovani qayta oching.",
  "error.ADMIN_REQUIRED": "Bu amal faqat adminlar uchun.",
  "error.REFERRAL_LOCKED": "Referral sharti bajarilmagan ({count}/{required}).",
  "error.PRO_REQUIRED": "Bu imkoniyat Pro tarif uchun.",
  "error.SAVE_LIMIT_REACHED": "Saqlash limiti tugadi ({current}/{limit}).",
  "error.PREMIUM_TEMPLATE": "Bu shablon Pro tarif uchun.",
  "error.INSUFFICIENT_BALANCE": "Balans yetarli emas: {required} so'm kerak, {balance} so'm bor.",
  "error.ALREADY_PRO": "Pro tarif allaqachon faol.",
  "error.NOT_FOUND": "Ma'lumot topilmadi.",
  "error.INVALID_UID": "Vakansiya identifikatori noto'g'ri.",
  "error.VALIDATION_ERROR": "Kiritilgan ma'lumotlar noto'g'ri.",
  "error.PAYLOAD_TOO_LARGE": "Fayl juda katta.",
  "error.TELEGRAM_SEND_FAILED": "Telegramga yuborib bo'lmadi. Botni ishga tushiring va qayta urining.",
  "error.UPSTREAM_ERROR": "Tashqi xizmat javob bermayapti. Birozdan so'ng urinib ko'ring.",
  "error.RATE_LIMITED": "Juda ko'p so'rov. Birozdan so'ng urinib ko'ring.",
  "error.NETWORK_ERROR": "Internet aloqasi yo'q. Aloqani tekshiring.",
  "error.BOT_START_REQUIRED": "Avval botda /start tugmasini bosing.",
  "error.SUBSCRIPTION_REQUIRED": "Avval majburiy kanallarga obuna bo'ling.",
  "error.USER_BANNED": "Hisobingiz bloklangan.",
  "error.UNKNOWN": "Xatolik yuz berdi. Qayta urinib ko'ring.",
};

export type CommonDict = typeof common;
export default common;
