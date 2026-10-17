/**
 * Vacancy labels + the integer code -> label maps.
 *
 * The code numbers are the osonish.uz codes and must stay in sync with
 * `src/functions/vacancy_format.py` (GENDER_MAP, WORK_TYPE_MAP,
 * BUSYNESS_TYPE_MAP, PAYMENT_TYPE_MAP, EDUCATION_MAP, EXPERIENCE_MAP).
 * `GET /api/jobs/{uid}` returns `data.normalized.codes` with the raw integers;
 * the frontend renders them through these maps (see `useVacancyLabels`).
 */
const vacancy = {
  // ── Card / detail UI ───────────────────────────────────────────────────────
  "vacancy.fallbackTitle": "Vakansiya",
  "vacancy.hidden": "Yashirilgan",
  "vacancy.open": "Batafsil ko'rish",
  "vacancy.openPro": "Batafsil ko'rish (Pro)",
  "vacancy.save": "Saqlash",
  "vacancy.saved": "Saqlangan",
  "vacancy.noRegion": "Hudud ko'rsatilmagan",
  "vacancy.description": "Tavsif",
  "vacancy.contacts": "Aloqa",
  "vacancy.lockedTitle": "Kontakt ma'lumotlari yashirilgan",
  "vacancy.lockedHint": "5 ta do'st taklif qiling yoki Pro tarifga o'ting",
  "vacancy.openInBot": "Botda ko'rish",
  "vacancy.goPro": "Pro tarifga o'tish",
  "vacancy.opening": "Ochilmoqda...",
  "vacancy.unknownCode": "Kod {code}",

  // ── Detail rows ────────────────────────────────────────────────────────────
  "vacancy.row.address": "Manzil",
  "vacancy.row.district": "Tuman/shahar",
  "vacancy.row.region": "Viloyat",
  "vacancy.row.workType": "Ish turi",
  "vacancy.row.busyness": "Bandlik",
  "vacancy.row.payment": "To'lov turi",
  "vacancy.row.experience": "Tajriba",
  "vacancy.row.education": "Ta'lim",
  "vacancy.row.gender": "Jins",
  "vacancy.row.age": "Yosh",
  "vacancy.row.workingHours": "Ish vaqti",
  "vacancy.row.count": "O'rinlar soni",
  "vacancy.row.deadline": "Muddati",
  "vacancy.row.postedAt": "E'lon sanasi",

  // ── Salary ─────────────────────────────────────────────────────────────────
  "vacancy.salary.negotiable": "Kelishiladi",
  "vacancy.salary.range": "{min} – {max} so'm",
  "vacancy.salary.from": "{min} so'mdan",

  // ── Code maps (source: src/functions/vacancy_format.py) ────────────────────
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
};

export type VacancyDict = typeof vacancy;
export default vacancy;
