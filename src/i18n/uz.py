# ============================================================
# src/i18n/uz.py — O'zbekcha (manba til)
# ============================================================

STRINGS: dict[str, str] = {
    # ── Umumiy ────────────────────────────────────────────────
    "common.yes": "Ha",
    "common.no": "Yo'q",
    "common.available": "Bor",
    "common.unavailable": "Yo'q",
    "common.not_available": "Mavjud emas",
    "common.back": "◀️ Orqaga",

    # ── Foydalanuvchi menyusi ─────────────────────────────────
    "menu.laws": "⚖️ Qonunchilik",
    "menu.hr": "💡 HR Maslahatlar",

    # ── /start ────────────────────────────────────────────────
    "start.loading_vacancy": "⏳ Vakansiya ma'lumotlari yuklanmoqda...",
    "start.bad_vacancy_link": "❌ Noto'g'ri vakansiya havolasi.",
    "start.vacancy_not_found": "❌ Vakansiya topilmadi yoki ma'lumot olishda xato.",
    "start.extra_sections": "Qo'shimcha bo'limlar:",
    "start.greeting": (
        "Assalomu alaykum, {name}!\n"
        "Botimizga xush kelibsiz. Kerakli bo'limni tanlang!"
    ),
    "start.subscribe_prompt": "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
    "start.btn.jobs": "💼 Ish qidirish",
    "start.btn.profile": "👤 Profil",
    "start.btn.saves": "🗂 Saqlanganlar",
    "start.btn.subscribed": "✅ Obuna bo'ldim",
    "start.channel_fallback": "Kanal",
    "start.check.ok": "✅ Tasdiqlandi!",
    "start.check.welcome": (
        "Xush kelibsiz, {name}!\n"
        "Endi botdan to'liq foydalanishingiz mumkin."
    ),
    "start.check.fail": (
        "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!\n"
        "Iltimos, barcha kanallarga obuna bo'ling."
    ),
    "start.developer": "Bot dasturchisi @coder_admin_py\n\nPowered by @coder_admin_py",

    # ── Referral ──────────────────────────────────────────────
    "referral.reward_notice": (
        "🎉 Yangi foydalanuvchi sizning havolangiz orqali qo'shildi!\n"
        "Hisobingizga <b>{reward} so'm</b> qo'shildi."
    ),
    "referral.gate": (
        "🔒 Botdan foydalanish uchun referral sharti yoqilgan.\n\n"
        "📊 Holat: {current}/{required}\n"
        "👥 Avval do'stlaringizni taklif qiling:\n"
        "{link}"
    ),

    # ── Til tanlash ───────────────────────────────────────────
    "lang.choose": "🌐 Tilni tanlang:",
    "lang.saved": "✅ Til o'zgartirildi: O'zbekcha",
    "lang.name.uz": "🇺🇿 O'zbekcha",
    "lang.name.ru": "🇷🇺 Русский",
    "lang.name.en": "🇬🇧 English",

    # ── Kontent: qonunchilik va HR ────────────────────────────
    "content.laws.header": (
        "📚 <b>O'zbekiston Mehnat Kodeksi</b>\n\nQiziqtirgan maqolani tanlang:"
    ),
    "content.laws.not_found": "Maqola topilmadi",
    "content.laws.read_more": "🔗 lex.uz'da o'qish",
    "content.truncated": "<i>... (to'liq o'qish uchun)</i>",
    "content.hr.header": (
        "🎯 <b>HR Maslahatlar</b>\n\nKariyerangizni rivojlantirish uchun amaliy tavsiyalar:"
    ),
    "content.hr.not_found": "Maslahat topilmadi",

    # ── Vakansiya: maoshlar va kodlar ─────────────────────────
    "vacancy.title_fallback": "Vakansiya",
    "vacancy.salary.range": "{min} – {max} so'm",
    "vacancy.salary.from": "{min} so'mdan",
    "vacancy.salary.upto": "{max} so'mgacha",
    "vacancy.salary.negotiable": "Kelishiladi",
    "vacancy.salary.unspecified": "Ko'rsatilmagan",
    "vacancy.code_unknown": "Kod {code}",

    "vacancy.gender.1": "Erkak",
    "vacancy.gender.2": "Ayol",
    "vacancy.gender.3": "Farqi yo'q",

    "vacancy.work_type.1": "Doimiy ish",
    "vacancy.work_type.2": "Vaqtinchalik ish",
    "vacancy.work_type.3": "Mavsumiy ish",

    "vacancy.busyness.1": "To'liq bandlik",
    "vacancy.busyness.2": "Qisman bandlik",

    "vacancy.payment.1": "Oylik",
    "vacancy.payment.2": "Kunlik",
    "vacancy.payment.3": "Soatbay",
    "vacancy.payment.4": "Ishbay",

    "vacancy.education.1": "Umumiy o'rta",
    "vacancy.education.2": "O'rta maxsus",
    "vacancy.education.3": "Bakalavr",
    "vacancy.education.4": "Magistr",

    "vacancy.experience.1": "Tajriba talab etilmaydi",
    "vacancy.experience.2": "1 yilgacha",
    "vacancy.experience.3": "1-3 yil",
    "vacancy.experience.4": "3+ yil",

    # ── Vakansiya: xabar yorliqlari ───────────────────────────
    "vacancy.label.company": "Tashkilot",
    "vacancy.label.salary": "Maosh",
    "vacancy.label.address": "Manzil",
    "vacancy.label.work_type": "Ish turi",
    "vacancy.label.busyness": "Bandlik",
    "vacancy.label.payment": "To'lov turi",
    "vacancy.label.education": "Ta'lim",
    "vacancy.label.experience": "Tajriba",
    "vacancy.label.gender": "Jins",
    "vacancy.label.count": "O'rinlar soni",
    "vacancy.label.hours": "Ish vaqti",
    "vacancy.label.posted": "E'lon sanasi",
    "vacancy.label.deadline": "Muddati",
    "vacancy.label.description": "Tavsif",
    "vacancy.label.contacts": "Aloqa",
    "vacancy.label.source": "Manba",
    "vacancy.label.phone": "Tel",
    "vacancy.label.email": "Email",

    # ── Bildirishnomalar ──────────────────────────────────────
    "notify.header": "📌 <b>Siz uchun ish tavsiyasi</b>",
    "notify.details": "Batafsil ko'rish",

    # ── Admin: tugmalar ───────────────────────────────────────
    "btn.admin.stats": "📊Statistika",
    "btn.admin.channels": "🔧Kanallar",
    "btn.admin.ads": "📤Reklama",
    "btn.admin.channel_add": "➕Kanal qo'shish",
    "btn.admin.channel_del": "❌Kanalni olib tashlash",
    "btn.admin.channel_list": "📋 Kanallar ro'yxati",
    "btn.admin.back": "🔙Orqaga qaytish",
    "btn.admin.forward": "📨Forward xabar yuborish",
    "btn.admin.copy": "📬Oddiy xabar yuborish",

    # ── Admin: xabarlar ───────────────────────────────────────
    "admin.hello": "Assalomu alaykum admin",
    "admin.main_menu": "Bosh menyu",
    "admin.choose": "Tanlang",
    "admin.channel_add_prompt": (
        "Kanal qo'shish uchun kanalning userini yuboring.\nMisol: @coder_admin"
    ),
    "admin.channel_del_prompt": (
        "O'chiriladigan kanalning userini yuboring.\nMisol: @coder_admin"
    ),
    "admin.cancelled": "Bekor qilindi",
    "admin.text_required": "Iltimos, matn ko'rinishida yuboring.",
    "admin.channel_bad_format": "Kanal useri xato! @coder_admin formatida kiriting",
    "admin.channel_exists": "Bu kanal allaqachon qo'shilgan",
    "admin.channel_added": "Kanal qo'shildi 🎉",
    "admin.channel_missing": "Bunday kanal yo'q",
    "admin.channel_deleted": "Kanal o'chirildi",
    "admin.channels_empty": "Hozircha kanallar yo'q",
    "admin.broadcast_menu": "Foydalanuvchilarga xabar yuborish bo'limi",
    "admin.forward_prompt": "Forward yuboriladigan xabarni yuboring",
    "admin.copy_prompt": "Yuborilishi kerak bo'lgan xabarni yuboring",
    "admin.sending": "Yuborilmoqda... {done}/{total}",
    "admin.progress": (
        "Yuborilmoqda... {done}/{total}\n"
        "✅ Muvaffaqiyatli: {ok}\n"
        "❌ Xato: {fail}"
    ),
    "admin.finished": (
        "✅ Yuborish yakunlandi!\n\n"
        "📊 Jami: {total} ta\n"
        "✅ Yuborildi: {ok} ta\n"
        "❌ Yuborilmadi: {fail} ta"
    ),
    "admin.stats.header": "📊 <b>Foydalanuvchilar statistikasi</b> 📊",
    "admin.stats.total": "Jami: {count} ta",
    "admin.stats.blocked": "🚫 Botni bloklaganlar: {count} ta",
    "admin.stats.last3m": "So'nggi 3 oy (Jami: {count} ta):",
    "admin.stats.last7d": "So'nggi 7 kun ({count} ta):",
    "admin.stats.row": "🔹 {label}: {count} ta",
    "admin.channels_status_header": "📊 Kanallar holati:",
    "admin.channels_db_empty": "❌ Bazada kanallar yo'q",
    "admin.diag.id": "ID",
    "admin.diag.admin": "Admin",
    "admin.diag.link": "Link",
    "admin.diag.error": "Xato",
    "admin.channel_info": (
        "Kanal useri: {username}\n"
        "Kanal nomi: {title}\n"
        "Kanal ID: {chat_id}\n"
        "Haqida: {about}"
    ),
    "admin.channel_no_admin": "Kanal {username} - botni admin qiling",
    "admin.channels_none": "Kanallar mavjud emas",

    # ── Haftalik statistika ───────────────────────────────────
    "stats.header": "📊 <b>Haftalik statistika</b> | {label}",
    "stats.users": "👥 <b>Foydalanuvchilar</b>",
    "stats.users_line": "   +{new} yangi (jami: {total} ta)",
    "stats.pro_line": "   💎 Pro: {count} ta",
    "stats.vacancies": "💼 <b>Vakansiyalar</b>",
    "stats.active_line": "   Aktiv e'lonlar: ~{count} ta",
    "stats.avg_salary_line": "   O'rtacha maosh: {amount} so'm",
    "stats.top_specs": "🏆 <b>Top sohalar:</b>",
    "stats.top_regions": "📍 <b>Top hududlar:</b>",
    "stats.top_row": "   {i}. {name} — {count} ta",
    "stats.resumes": "📄 Resume yaratildi: {count}",
    "stats.saves": "❤️ Saqlangan: {count} ta",
    "stats.week_short": "{day}-{month}",
    "stats.week_range_same_month": "{d1}–{d2} {month} {year}",
    "stats.week_range": "{d1} {month1} – {d2} {month2} {year}",

    # ── Oy nomlari ────────────────────────────────────────────
    "month.1": "yanvar",
    "month.2": "fevral",
    "month.3": "mart",
    "month.4": "aprel",
    "month.5": "may",
    "month.6": "iyun",
    "month.7": "iyul",
    "month.8": "avgust",
    "month.9": "sentabr",
    "month.10": "oktabr",
    "month.11": "noyabr",
    "month.12": "dekabr",

    # ── Chart / grafik ────────────────────────────────────────
    "chart.title": "Haftalik statistika — {label}",
    "chart.top_specs": "Top sohalar",
    "chart.top_regions": "Top hududlar",
    "chart.new_users": "Haftalik yangi foydalanuvchilar",
    "chart.avg_salary": "O'rtacha maosh (so'm)",
}
