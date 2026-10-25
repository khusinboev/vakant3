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
    "common.back": "Orqaga",

    # ── Foydalanuvchi menyusi ─────────────────────────────────
    "menu.laws": "Qonunchilik",
    "menu.hr": "HR Maslahatlar",

    # ── /start ────────────────────────────────────────────────
    "start.loading_vacancy": "{e:hourglass} Vakansiya ma'lumotlari yuklanmoqda...",
    "start.bad_vacancy_link": "❌ Noto'g'ri vakansiya havolasi.",
    "start.vacancy_not_found": "❌ Vakansiya topilmadi yoki ma'lumot olishda xato.",
    "start.greeting": (
        "{e:wave} Assalomu alaykum, <b>{name}</b>!\n\n"
        "Bandlik.uz botida vakansiyalarni qidiring, saqlang va yangi ishlar haqida xabar oling.\n"
        "{e:laws} Mehnat qonunchiligi va {e:tips} HR maslahatlar pastdagi menyuda."
    ),
    "start.subscribe_prompt": "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
    "start.btn.open_app": "Ilovada ochish",
    "start.btn.open_in_bot": "Botda batafsil",
    "start.btn.apply": "Ariza topshirish",
    "bot.menu_button": "Ilova",
    "cmd.start": "Botni boshlash",
    "cmd.lang": "Tilni o'zgartirish",
    "cmd.admin": "Admin panel",
    "start.btn.jobs": "Ish qidirish",
    "start.btn.profile": "Profil",
    "start.btn.saves": "Saqlanganlar",
    "start.btn.subscribed": "Obuna bo'ldim",
    "start.channel_fallback": "Kanal",
    "start.check.ok": "✅ Tasdiqlandi!",
    "start.check.welcome": (
        "{e:party} Xush kelibsiz, <b>{name}</b>!\n"
        "Endi botdan to'liq foydalanishingiz mumkin."
    ),
    "start.check.fail": (
        "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!\n"
        "Iltimos, barcha kanallarga obuna bo'ling."
    ),
    "start.developer": "Bot dasturchisi @coder_admin_py\n\nPowered by @coder_admin_py",

    # ── Referral ──────────────────────────────────────────────
    "referral.reward_notice": (
        "{e:party} Yangi foydalanuvchi sizning havolangiz orqali qo'shildi!\n"
        "{e:wallet} Hisobingizga <b>{reward} so'm</b> qo'shildi."
    ),
    "referral.gate": (
        "{e:lock} Botdan foydalanish uchun referral sharti yoqilgan.\n\n"
        "{e:stats} Holat: {current}/{required}\n"
        "{e:group} Avval do'stlaringizni taklif qiling:\n"
        "{link}"
    ),
    "referral.btn.share": "Do'stlarga ulashish",
    "referral.share_text": "Bandlik.uz — vakansiyalar va ish e'lonlari boti. Qo'shiling!",

    # ── Til tanlash ───────────────────────────────────────────
    "lang.choose": "{e:lang} Tilni tanlang:",
    "lang.saved": "✅ Til o'zgartirildi: O'zbekcha",
    "lang.name.uz": "🇺🇿 O'zbekcha",
    "lang.name.ru": "🇷🇺 Русский",
    "lang.name.en": "🇬🇧 English",

    # ── Kontent: qonunchilik va HR ────────────────────────────
    "content.laws.header": (
        "{e:laws} <b>O'zbekiston Mehnat Kodeksi</b>\n\n"
        "Qiziqtirgan maqolani tanlang:"
    ),
    "content.laws.not_found": "Maqola topilmadi",
    "content.laws.read_more": "lex.uz'da o'qish",
    "content.truncated": "<i>... (to'liq o'qish uchun)</i>",
    "content.hr.header": (
        "{e:tips} <b>HR Maslahatlar</b>\n\n"
        "Kariyerangizni rivojlantirish uchun amaliy tavsiyalar:"
    ),
    "content.hr.not_found": "Maslahat topilmadi",

    # ── Vakansiya: maoshlar va kodlar ─────────────────────────
    "vacancy.title_fallback": "Vakansiya",
    "vacancy.salary.range": "{min} – {max} so'm",
    "vacancy.salary.from": "{min} so'mdan",
    "vacancy.salary.upto": "{max} so'mgacha",
    "vacancy.salary.negotiable": "Kelishiladi",
    "vacancy.salary.unspecified": "Ko'rsatilmagan",
    "vacancy.salary.cur_range": "{min} – {max} {cur}",
    "vacancy.salary.cur_from": "{min} {cur} dan",
    "vacancy.salary.cur_upto": "{max} {cur} gacha",
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

    # hh.uz dictionary ids (experience / employment / schedule)
    "vacancy.hh.experience.noExperience": "Tajriba talab etilmaydi",
    "vacancy.hh.experience.between1And3": "1–3 yil",
    "vacancy.hh.experience.between3And6": "3–6 yil",
    "vacancy.hh.experience.moreThan6": "6 yildan ortiq",
    "vacancy.hh.employment.full": "To'liq bandlik",
    "vacancy.hh.employment.part": "Qisman bandlik",
    "vacancy.hh.employment.project": "Loyiha bo'yicha ish",
    "vacancy.hh.employment.volunteer": "Ko'ngillilik",
    "vacancy.hh.employment.probation": "Amaliyot (stajirovka)",
    "vacancy.hh.schedule.fullDay": "To'liq kun",
    "vacancy.hh.schedule.shift": "Smenali grafik",
    "vacancy.hh.schedule.flexible": "Moslashuvchan grafik",
    "vacancy.hh.schedule.remote": "Masofaviy ish",
    "vacancy.hh.schedule.flyInFlyOut": "Vaxta usuli",

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
    "vacancy.openings": "{n} ta o'rin",
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
    "notify.header": "{e:bell} <b>Siz uchun ish tavsiyasi</b>",
    "notify.details": "Batafsil ko'rish",

    # ── Admin: tugmalar ───────────────────────────────────────
    "btn.admin.stats": "Statistika",
    "btn.admin.channels": "Kanallar",
    "btn.admin.ads": "Reklama",
    "btn.admin.channel_add": "Kanal qo'shish",
    "btn.admin.channel_del": "Kanalni olib tashlash",
    "btn.admin.channel_list": "Kanallar ro'yxati",
    "btn.admin.back": "Orqaga qaytish",

    # ── Admin: xabarlar ───────────────────────────────────────
    "admin.hello": "{e:admin} Assalomu alaykum admin",
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
    "admin.channel_added": "{e:party} Kanal qo'shildi",
    "admin.channel_missing": "Bunday kanal yo'q",
    "admin.channel_deleted": "Kanal o'chirildi",
    "admin.channels_empty": "Hozircha kanallar yo'q",
    "admin.broadcast_menu": "Foydalanuvchilarga xabar yuborish bo'limi",
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
    "admin.stats.header": "{e:stats} <b>Foydalanuvchilar statistikasi</b>",
    "admin.stats.total": "Jami: {count} ta",
    "admin.stats.blocked": "🚫 Botni bloklaganlar: {count} ta",
    "admin.stats.last3m": "So'nggi 3 oy (Jami: {count} ta):",
    "admin.stats.last7d": "So'nggi 7 kun ({count} ta):",
    "admin.stats.row": "🔹 {label}: {count} ta",
    "menu.admin": "Admin",
    "btn.admin.exit": "Asosiy menyu",
    "menu.refreshed": "{e:sparkles} Menyu yangilandi.",
    "stats2.title": "{e:stats} Statistika",
    "stats2.sec.users": "Foydalanuvchilar",
    "stats2.sec.pro": "Pro",
    "stats2.sec.payments": "To'lovlar",
    "stats2.sec.wallet": "Hamyon harakati (30 kun)",
    "stats2.sec.referrals": "Referallar",
    "stats2.sec.broadcasts": "So'nggi xabarlar",
    "stats2.users.total": "Jami",
    "stats2.users.today": "Bugun yangi",
    "stats2.users.d7": "7 kunda yangi",
    "stats2.users.d30": "30 kunda yangi",
    "stats2.users.active7": "7 kunda faol",
    "stats2.users.blocked": "Botni bloklagan",
    "stats2.users.banned": "Ban qilingan",
    "stats2.pro.count": "Pro foydalanuvchilar",
    "stats2.pro.act7": "Faollashtirish (7 kun)",
    "stats2.pro.act30": "Faollashtirish (30 kun)",
    "stats2.pay.period": "Davr",
    "stats2.pay.paid": "To'langan",
    "stats2.pay.sum": "Summa",
    "stats2.period.today": "Bugun",
    "stats2.period.d7": "7 kun",
    "stats2.period.d30": "30 kun",
    "stats2.period.all": "Jami",
    "stats2.pay.pending": "Kutilmoqda",
    "stats2.pay.cancelled": "Bekor qilingan",
    "stats2.pay.by_method": "Usul bo'yicha (jami)",
    "stats2.method.page": "Sahifa",
    "stats2.method.card": "Karta",
    "stats2.method.phone": "Telefon",
    "stats2.method.app": "Ilova",
    "stats2.method.unknown": "Boshqa",
    "stats2.wallet.topup": "To'ldirishlar",
    "stats2.wallet.topup_bonus": "To'ldirish bonuslari",
    "stats2.wallet.pro_activation": "Pro faollashtirish",
    "stats2.wallet.referral_reward": "Referal mukofotlari",
    "stats2.ref.new30": "Yangi referallar (30 kun)",
    "stats2.bc.none": "Hali xabar yuborilmagan",
    "stats2.bc.row": "#{id} {status}: yuborildi {sent}, xato {failed}",
    "stats2.money": "{amount} so'm",
    "stats2.col.metric": "Ko'rsatkich",
    "stats2.col.value": "Qiymat",
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

    # ── Admin: broadcast wizard ───────────────────────────────
    "btn.admin.bc_new": "Yangi xabar",
    "btn.admin.bc_list": "Xabarlar",
    "btn.admin.webapp": "Admin panelni ochish",
    "admin.webapp_hint": "{e:app} Kengaytirilgan boshqaruv Mini App ichida:",
    "admin.denied": "⛔ Bu amal uchun ruxsatingiz yo'q.",
    "bc.prompt_content": "Yuboriladigan xabarni yuboring: matn, rasm, video, hujjat yoki GIF.\nFormatlash va emojilar saqlanadi.",
    "bc.bad_content": "Bu turdagi xabar qo'llab-quvvatlanmaydi. Matn, rasm, video, hujjat yoki GIF yuboring.",
    "bc.album_unsupported": "Albom (bir nechta rasm yoki video) qo'llab-quvvatlanmaydi. Bitta xabar yuboring: bitta rasm, video yoki hujjat, kerak bo'lsa izoh bilan.",
    "bc.prompt_button": "Tugma qo'shish uchun <code>Matn | https://...</code> ko'rinishida yuboring yoki «O'tkazib yuborish» ni bosing.",
    "bc.bad_button": "Tugma formati xato. Misol: <code>Batafsil | https://bandlik.uz</code> (matn 64 belgigacha, havola http yoki https).",
    "bc.prompt_audience": "{e:group} Kimga yuboramiz?",
    "bc.empty_segment": "Bu auditoriyada qabul qiluvchi yo'q. Boshqasini tanlang.",
    "bc.preview_card": "👆 Xabar foydalanuvchilarga shunday ko'rinadi.\n\n👥 Auditoriya: {segment}\n📨 Qabul qiluvchilar: <b>{count}</b>\n🔘 Tugma: {button}\n\nYuborishdan oldin «🧪 O'zimga sinov» bilan tekshirib ko'ring.",
    "bc.no_button": "yo'q",
    "bc.preview_failed": "Xabarni nusxalab bo'lmadi (o'chirilgan bo'lishi mumkin). Qaytadan boshlang.",
    "bc.expired": "Bu amal eskirgan. Qaytadan boshlang.",
    "bc.test_sent": "🧪 Sinov xabari sizga yuborildi",
    "bc.test_failed": "Sinov xabarini yuborib bo'lmadi",
    "bc.already_queued": "Bu xabar allaqachon navbatga qo'yilgan",
    "bc.queued": "✅ Navbatga qo'yildi: {total} ta qabul qiluvchi",
    "bc.card": "📣 <b>Xabar #{id}</b> · {status}\n👥 {segment}\n\n{body}",
    "bc.status.draft": "📝 qoralama",
    "bc.status.queued": "⏳ navbatda",
    "bc.status.running": "🚀 yuborilmoqda",
    "bc.status.paused": "⏸ to'xtatib turilgan",
    "bc.status.cancelled": "✖ to'xtatilgan",
    "bc.status.done": "✅ yakunlangan",
    "bc.status.failed": "❌ xato",
    "bc.state_changed": "Holat: {status}",
    "bc.state_unchanged": "Hozirgi holatda bu amalni bajarib bo'lmaydi",
    "bc.stop_confirm": "\n\n⚠️ Xabarni butunlay to'xtatasizmi? Buni qaytarib bo'lmaydi.",
    "bc.list_header": "{e:list} <b>So'nggi xabarlar</b>",
    "bc.list_row": "#{id} · {status} · {done}/{total}",
    "bc.list_empty": "Hozircha xabarlar yo'q",
    "bc.btn.skip": "O'tkazib yuborish",
    "bc.btn.cancel": "Bekor qilish",
    "bc.btn.test": "O'zimga sinov",
    "bc.btn.send": "{count} kishiga yuborish",
    "bc.btn.pause": "Pauza",
    "bc.btn.resume": "Davom ettirish",
    "bc.btn.stop": "To'xtatish",
    "bc.btn.stop_yes": "Ha, to'xtatish",
    "bc.btn.stop_no": "Yo'q",
    "bc.btn.refresh": "Yangilash",
    "bc.seg.all": "👥 Hammasi",
    "bc.seg.pro": "⭐ Pro",
    "bc.seg.free": "🆓 Bepul",
    "bc.seg.lang_uz": "🇺🇿 O'zbekcha",
    "bc.seg.lang_ru": "🇷🇺 Ruscha",
    "bc.seg.lang_en": "🇬🇧 Inglizcha",
    "bc.seg.active_7": "🔥 Faol (7 kun)",
    "bc.seg.active_30": "📆 Faol (30 kun)",
    "bc.seg.test_admins": "🧪 Faqat adminlar (sinov)",

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
