import type { VacancyDict } from "../uz/vacancy";

const vacancy: Record<keyof VacancyDict, string> = {
  // ── Card / detail UI ───────────────────────────────────────────────────────
  "vacancy.fallbackTitle": "Вакансия",
  "vacancy.hidden": "Скрыто",
  "vacancy.open": "Подробнее",
  "vacancy.openPro": "Подробнее (Pro)",
  "vacancy.save": "Сохранить",
  "vacancy.saved": "Сохранено",
  "vacancy.noRegion": "Регион не указан",
  "vacancy.description": "Описание",
  "vacancy.contacts": "Контакты",
  "vacancy.lockedTitle": "Контактные данные скрыты",
  "vacancy.lockedHint": "Пригласите 5 друзей или перейдите на тариф Pro",
  "vacancy.openInBot": "Открыть в боте",
  "vacancy.goPro": "Перейти на Pro",
  "vacancy.opening": "Открываем...",
  "vacancy.unknownCode": "Код {code}",

  // ── Detail rows ────────────────────────────────────────────────────────────
  "vacancy.row.address": "Адрес",
  "vacancy.row.district": "Район/город",
  "vacancy.row.region": "Область",
  "vacancy.row.workType": "Тип работы",
  "vacancy.row.busyness": "Занятость",
  "vacancy.row.payment": "Тип оплаты",
  "vacancy.row.experience": "Опыт",
  "vacancy.row.education": "Образование",
  "vacancy.row.gender": "Пол",
  "vacancy.row.age": "Возраст",
  "vacancy.row.workingHours": "Рабочее время",
  "vacancy.row.count": "Количество мест",
  "vacancy.row.deadline": "Срок",
  "vacancy.row.postedAt": "Дата публикации",

  // ── Salary ─────────────────────────────────────────────────────────────────
  "vacancy.salary.negotiable": "По договорённости",
  "vacancy.salary.range": "{min} – {max} сум",
  "vacancy.salary.from": "от {min} сум",

  // ── Code maps ──────────────────────────────────────────────────────────────
  "vacancy.gender.1": "Мужской",
  "vacancy.gender.2": "Женский",
  "vacancy.gender.3": "Не важно",

  "vacancy.work_type.1": "Постоянная работа",
  "vacancy.work_type.2": "Временная работа",
  "vacancy.work_type.3": "Сезонная работа",

  "vacancy.busyness.1": "Полная занятость",
  "vacancy.busyness.2": "Частичная занятость",

  "vacancy.payment.1": "Ежемесячно",
  "vacancy.payment.2": "Ежедневно",
  "vacancy.payment.3": "Почасово",
  "vacancy.payment.4": "Сдельно",

  "vacancy.education.1": "Среднее общее",
  "vacancy.education.2": "Среднее специальное",
  "vacancy.education.3": "Бакалавр",
  "vacancy.education.4": "Магистр",

  "vacancy.experience.1": "Опыт не требуется",
  "vacancy.experience.2": "До 1 года",
  "vacancy.experience.3": "1–3 года",
  "vacancy.experience.4": "3+ года",
};

export default vacancy;
