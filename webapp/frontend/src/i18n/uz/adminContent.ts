/** adminContent namespace — Content page (articles/tips/categories CRUD). uz is the source. */
const adminContent = {
  // ── List screen ────────────────────────────────────────────────────────────
  "adminContent.tabs.aria": "Kontent bo'limlari",
  "adminContent.tab.articles": "Maqolalar",
  "adminContent.tab.tips": "Maslahatlar",
  "adminContent.tab.categories": "Kategoriyalar",

  "adminContent.list.searchPlaceholder": "ID yoki sarlavha bo'yicha qidirish",
  "adminContent.list.category": "Kategoriya",
  "adminContent.list.published": "Chop etilgan",
  "adminContent.list.unpublished": "Chop etilmagan",
  "adminContent.list.sort": "Tartib",

  "adminContent.filter.yes": "Ha",
  "adminContent.filter.no": "Yo'q",

  "adminContent.new.article": "Yangi",
  "adminContent.new.tip": "Yangi",
  "adminContent.new.category": "Yangi",

  "adminContent.empty.articles": "Hozircha maqolalar yo'q.",
  "adminContent.empty.tips": "Hozircha maslahatlar yo'q.",
  "adminContent.empty.categories": "Hozircha kategoriyalar yo'q.",

  // ── Editor sections ──────────────────────────────────────────────────────
  "adminContent.section.basic": "Asosiy",
  "adminContent.section.titles": "Sarlavha va qisqacha",
  "adminContent.section.name": "Nomi",
  "adminContent.section.body": "Matn",
  "adminContent.section.source": "Manba",

  // ── Editor chrome ────────────────────────────────────────────────────────
  "adminContent.editor.backToList": "Ro'yxatga qaytish",
  "adminContent.editor.unsavedBadge": "Saqlanmagan o'zgarishlar bor",
  "adminContent.editor.save": "Saqlash",
  "adminContent.editor.delete": "O'chirish",
  "adminContent.editor.deleteTitle": "O'chirishni tasdiqlaysizmi?",
  "adminContent.editor.deleteDesc": "\"{id}\" butunlay o'chiriladi. Bu amalni ortga qaytarib bo'lmaydi.",
  "adminContent.editor.deleteConfirm": "Ha, o'chirilsin",
  "adminContent.editor.discardTitle": "Saqlanmagan o'zgarishlar bor",
  "adminContent.editor.discardDesc": "Chiqib ketsangiz, kiritilgan o'zgarishlar yo'qoladi.",
  "adminContent.editor.discardConfirm": "Ha, bekor qilinsin",

  "adminContent.editor.newArticleTitle": "Yangi maqola",
  "adminContent.editor.newTipTitle": "Yangi maslahat",
  "adminContent.editor.newCategoryTitle": "Yangi kategoriya",

  "adminContent.editor.idLabel": "ID (slug)",
  "adminContent.editor.idHint": "faqat lotin harflari, raqam va chiziqcha, 3-60 belgi",
  "adminContent.editor.idInvalid": "ID faqat kichik lotin harflari, raqam va \"-\" dan iborat bo'lishi kerak (3-60 belgi).",
  "adminContent.editor.categoryLabel": "Kategoriya",
  "adminContent.editor.categoryPlaceholder": "Kategoriyani tanlang",
  "adminContent.editor.sortOrderLabel": "Tartib raqami",
  "adminContent.editor.sourceUrlLabel": "Manba havolasi",
  "adminContent.editor.optionalHint": "(ixtiyoriy)",
  "adminContent.editor.publishedLabel": "Chop etilgan",
  "adminContent.editor.langTabs": "Til",
  "adminContent.editor.copyFromUz": "O'zbekchadan nusxalash",

  "adminContent.editor.created": "Yaratildi.",
  "adminContent.editor.saved": "Saqlandi.",
  "adminContent.editor.deleted": "O'chirildi.",

  "adminContent.editor.fieldTitle": "Sarlavha",
  "adminContent.editor.fieldSummary": "Qisqacha mazmun",
  "adminContent.editor.fieldFullText": "To'liq matn",
  "adminContent.editor.fieldSourceLabel": "Manba nomi",
  "adminContent.editor.fieldName": "Nomi",

  // ── Rich-text toolbar ────────────────────────────────────────────────────
  "adminContent.toolbar.aria": "Matn formatlash paneli",
  "adminContent.toolbar.bold": "Qalin",
  "adminContent.toolbar.italic": "Kursiv",
  "adminContent.toolbar.underline": "Tag chizilgan",
  "adminContent.toolbar.code": "Kod",
  "adminContent.toolbar.link": "Havola",
  "adminContent.toolbar.br": "Qator ko'chirish",
  "adminContent.toolbar.showPreview": "Ko'rib chiqish",
  "adminContent.toolbar.hidePreview": "Tahrirlashga qaytish",
  "adminContent.toolbar.invalidHtml": "Ruxsat etilmagan belgilash: faqat <b> <i> <u> <a href> <code> <br> mumkin.",
  "adminContent.toolbar.linkPrompt": "Havola manzili (https://...)",
  "adminContent.toolbar.linkSample": "havola matni",
  "adminContent.toolbar.sample": "matn",

  // ── Server error mapping (CONTENT_EXISTS / CONTENT_IN_USE / VALIDATION_ERROR) ──
  "adminContent.error.validation": "Bu maydon noto'g'ri to'ldirilgan yoki juda uzun.",
  "adminContent.error.exists": "Bu ID band. Boshqasini tanlang.",
  "adminContent.error.inUse": "Bu kategoriyada maqolalar bor — avval ularni ko'chiring yoki o'chiring.",
  "adminContent.error.notFound": "Yozuv topilmadi — ro'yxat yangilandi.",
};
export type AdminContentDict = typeof adminContent;
export default adminContent;
