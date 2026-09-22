/** Admin namespace — uz is the source language (see src/i18n/index.ts). */
const admin = {
  // ── Shell ──────────────────────────────────────────────────────────────────
  "admin.title": "Admin panel",
  "admin.accessDenied": "Admin panel faqat adminlar uchun.",


  "admin.status.on": "Faol",
  "admin.status.off": "O'chiq",

  // ── Dashboard (v3) ─────────────────────────────────────────────────────────
  "admin.dash.sparklineAria": "Oxirgi 7 kunlik yangi foydalanuvchilar grafigi",
  "admin.dash.sparklineLabel": "Yangi foydalanuvchilar — 7 kun",
  "admin.dash.systemOk": "Tizim barqaror",
  "admin.dash.systemDegraded": "Tizimda muammo bor",
  "admin.dash.systemUnknown": "Tizim holati noma'lum",
  "admin.dash.autoPostLabel": "Avto-post",
  "admin.dash.postedTodayLabel": "Bugun joylandi",
  "admin.dash.referralLabel": "Referral",
  "admin.dash.minReferralsLabel": "Min. referal",

  // ── Overview ───────────────────────────────────────────────────────────────
  "admin.overview.kpiTitle": "Rezyume KPI maqsadlari",

  "admin.kpi.completion": "Yakunlash",
  "admin.kpi.sendSuccess": "Yuborish muvaffaqiyati",
  "admin.kpi.pdfExport": "PDF eksport",
  "admin.kpi.creationTime": "Tayyorlash vaqti",
  "admin.kpi.minutesShort": "daq",
  "admin.kpi.openedUsers": "Ochgan",
  "admin.kpi.completedUsers": "Yakunlagan",
  "admin.kpi.sendAttempts": "Yuborgan",

  // ── Settings ───────────────────────────────────────────────────────────────
  "admin.settings.group.autoPost": "Avto-post",
  "admin.settings.group.referralGate": "Referral shart",
  "admin.settings.group.pro": "Pro tarif",
  "admin.settings.group.resumeKpi": "Rezyume KPI maqsadlari",

  "admin.settings.field.enabled": "Faol",
  "admin.settings.field.channel": "Kanal",
  "admin.settings.field.channelLang": "Kanal tili",
  "admin.settings.field.autoPostMinSalary": "Eng kam maosh (so'm)",
  "admin.settings.field.perDayMin": "Kuniga eng kam",
  "admin.settings.field.perDayMax": "Kuniga eng ko'p",
  "admin.settings.field.requiredRefs": "Talab qilinadigan referallar",
  "admin.settings.field.proPrice": "Pro narxi (so'm)",
  "admin.settings.field.referralReward": "Referal mukofoti (so'm)",
  "admin.settings.field.proMinSalary": "Pro uchun eng kam maosh (so'm)",
  "admin.settings.field.targetCreationMinutes": "Tayyorlash vaqti (daq)",
  "admin.settings.field.targetCompletionRate": "Yakunlash darajasi (%)",
  "admin.settings.field.targetSendRate": "Yuborish muvaffaqiyati (%)",
  "admin.settings.field.targetExportRate": "PDF eksport muvaffaqiyati (%)",

  "admin.settings.editAria": "{label} — tahrirlash",
  "admin.settings.saved": "Sozlama saqlandi.",
  "admin.settings.saving": "Saqlanmoqda…",
  "admin.settings.conflict.message": "Sozlama boshqa joyda o'zgartirildi.",
  "admin.settings.conflict.reload": "Qayta yuklash",
  "admin.settings.validation.number": "{label}: raqam kiriting.",
  "admin.settings.validation.negative": "{label}: manfiy bo'lishi mumkin emas.",
  "admin.settings.validation.empty": "{label}: qiymat bo'sh bo'lishi mumkin emas.",
  "admin.settings.validation.perDayRange":
    "Kuniga eng kam qiymat eng ko'pdan katta bo'lmasligi kerak ({min} > {max}).",

  // ── Analytics ──────────────────────────────────────────────────────────────
  "admin.analytics.opsTitle": "Amallar (24 soat)",
  "admin.analytics.success": "Muvaffaqiyatli",
  "admin.analytics.error": "Xatolik",
  "admin.analytics.opSave": "Saqlash",
  "admin.analytics.opSend": "Yuborish",
  "admin.analytics.opExport": "Eksport",
  "admin.analytics.activeUsers": "Faol foydalanuvchi",
  "admin.analytics.opened": "Ochilgan",
  "admin.analytics.ready": "Tayyor",
  "admin.analytics.latencyTitle": "Kechikish (o'rtacha)",
  "admin.analytics.funnelTitle": "Voronka ({hours} soat)",
  "admin.analytics.funnelEmpty": "Voronka ma'lumotlari yo'q.",
  "admin.analytics.diagTitle": "Diagnostika xatoliklari",
  "admin.analytics.diagCount": "{n} marta",
  "admin.analytics.noErrors": "Oxirgi 24 soatda xatolik topilmadi.",

  "admin.latency.ttfi": "TTFI",
  "admin.latency.save": "Saqlash",
  "admin.latency.send": "Yuborish",
  "admin.latency.export": "Eksport",
  "admin.latency.unit": "ms",

  "admin.funnel.entered": "{n} kirdi",
  "admin.funnel.dropped": "{n} chiqib ketdi",
  "admin.funnel.step.basic": "Asosiy ma'lumot",
  "admin.funnel.step.experience": "Tajriba",
  "admin.funnel.step.education": "Ta'lim",
  "admin.funnel.step.skills": "Ko'nikmalar",
  "admin.funnel.step.summary": "Qisqacha",
  "admin.funnel.step.template": "Shablon",
  "admin.funnel.step.final": "Yakuniy",

  // ── Users ──────────────────────────────────────────────────────────────────

  // ── Shell v2 (AdminLayout / registry / shared components) ─────────────────
  "admin.nav.aria": "Admin bo'limlari",
  "admin.nav.group.main": "Asosiy",
  "admin.nav.group.people": "Foydalanuvchilar",
  "admin.nav.group.content": "Kontent va kanallar",
  "admin.nav.group.money": "Moliya",
  "admin.nav.group.system": "Tizim",

  "admin.nav.overview": "Boshqaruv paneli",
  "admin.nav.analytics": "Analitika",
  "admin.nav.resume": "Rezyume analitikasi",
  "admin.nav.users": "Foydalanuvchilar",
  "admin.nav.broadcasts": "Xabar yuborish",
  "admin.nav.channels": "Kanallar",
  "admin.nav.autopost": "Avto-post",
  "admin.nav.content": "Kontent",
  "admin.nav.finance": "Moliya",
  "admin.nav.system": "Tizim",
  "admin.nav.settings": "Sozlamalar",

  "admin.role.owner": "Egasi",
  "admin.role.admin": "Admin",
  "admin.role.moderator": "Moderator",
  "admin.role.viewer": "Kuzatuvchi",
  "admin.role.required": "Bu bo'lim uchun kamida \"{role}\" roli kerak.",

  "admin.shell.openPanel": "Admin panelni ochish",

  "admin.table.empty": "Ma'lumot topilmadi.",
  "admin.table.loadMore": "Yana yuklash",
  "admin.table.loadingMore": "Yuklanmoqda...",
  "admin.table.total": "Jami: {total}",

  "admin.confirm.title": "Amalni tasdiqlaysizmi?",
  "admin.confirm.confirm": "Tasdiqlash",
  "admin.confirm.cancel": "Bekor qilish",
  "admin.confirm.working": "Bajarilmoqda...",

  "admin.filter.searchPlaceholder": "Qidirish...",
  "admin.filter.all": "Barchasi",
  "admin.filter.from": "Sanadan",
  "admin.filter.to": "Sanagacha",

  "admin.empty.default": "Hozircha hech nima yo'q.",
  "admin.stat.deltaUp": "{value} o'sish",
  "admin.stat.deltaDown": "{value} pasayish",


  // ── Analytics dashboard (daily_stats rollup) ────────────────────────────────
  "admin.analytics2.stat.groupLabel": "Bugungi ko'rsatkichlar",
  "admin.analytics2.stat.hintToday": "bugun",
  "admin.analytics2.stat.newUsers": "Yangi foydalanuvchilar",
  "admin.analytics2.stat.activeUsers": "Faol foydalanuvchilar",
  "admin.analytics2.stat.proUsers": "Pro foydalanuvchilar",
  "admin.analytics2.stat.revenue": "Daromad",
  "admin.analytics2.stat.saves": "Saqlanganlar",
  "admin.analytics2.stat.resumeSendsOk": "Rezyume yuborildi",
  "admin.analytics2.stat.resumeSendsErr": "Rezyume xatoliklari",
  "admin.analytics2.stat.autoPosts": "Avto-postlar",
  "admin.analytics2.stat.notifications": "Bildirishnomalar",

  "admin.analytics2.chart.usersTitle": "Foydalanuvchilar",
  "admin.analytics2.chart.usersAria": "Kunlik yangi va faol foydalanuvchilar grafigi",
  "admin.analytics2.chart.usersNew": "Yangi",
  "admin.analytics2.chart.usersActive": "Faol",
  "admin.analytics2.chart.revenueTitle": "Daromad",
  "admin.analytics2.chart.revenueAria": "Kunlik daromad grafigi",
  "admin.analytics2.chart.resumeSendsTitle": "Rezyume yuborilishi",
  "admin.analytics2.chart.resumeSendsAria": "Kunlik muvaffaqiyatli va xato rezyume yuborishlar grafigi",
  "admin.analytics2.chart.resumeOk": "Muvaffaqiyatli",
  "admin.analytics2.chart.resumeErr": "Xatolik",
  "admin.analytics2.chart.notifTitle": "Bildirishnoma va avto-postlar",
  "admin.analytics2.chart.notifAria": "Kunlik bildirishnomalar va avto-postlar grafigi",
  "admin.analytics2.chart.notifNotifications": "Bildirishnomalar",
  "admin.analytics2.chart.notifAutoPosts": "Avto-postlar",

  "admin.analytics2.empty.title": "Statistika hali hisoblanmagan",
  "admin.analytics2.empty.description":
    "Kunlik yig'ish (rollup) hali ishga tushmagan — grafiklar birinchi kun yakunlangach paydo bo'ladi.",

  "admin.analytics2.resumeKpi.title": "Rezyume KPI ko'rsatkichlari",

  // ── Shell v3 (AdminShell / AdminBar / Rail / ui kit) ─────────────────────
  "admin.shell.back": "Orqaga",
  "admin.shell.menu": "Yana amallar",
  "admin.shell.actions": "Amallar",
  "admin.shell.content": "Admin kontenti",

  "admin.bar.home": "Bosh",
  "admin.bar.users": "Odamlar",
  "admin.bar.broadcasts": "Xabar",
  "admin.bar.more": "Ko'proq",

  "admin.more.title": "Bo'limlar",
  "admin.more.quickActions": "Tezkor amallar",
  "admin.more.quick.postNow": "Hozir joylash",
  "admin.more.quick.newBroadcast": "Yangi xabar",
  "admin.more.quick.addChannel": "Kanal qo'shish",

  "admin.rail.pin": "Menyuni qotirish",
  "admin.rail.unpin": "Menyuni yig'ish",

  "admin.sheet.close": "Yopish",

  "admin.filter.title": "Filtrlar",
  "admin.filter.open": "Filtrlar",
  "admin.filter.openCount": "Filtrlar ({count})",
  "admin.filter.apply": "Qo'llash",
  "admin.filter.clear": "Tozalash",
  "admin.filter.removeAria": "{label} filtrini olib tashlash",
  "admin.filter.on": "Yoqilgan",

  "admin.search.clear": "Qidiruvni tozalash",

  "admin.tabs.aria": "Bo'limlar",
  "admin.toolbar.more": "Yana",
  "admin.toolbar.moreAria": "Qo'shimcha amallar",

  "admin.period.aria": "Davr",
  "admin.period.7": "7 kun",
  "admin.period.30": "30 kun",
  "admin.period.90": "90 kun",
  "admin.period.365": "1 yil",


};
export type AdminDict = typeof admin;
export default admin;
