import type { AdminAutopostDict } from "../uz/adminAutopost";

const adminAutopost: Record<keyof AdminAutopostDict, string> = {
  "adminAutopost.status.enabledLabel": "Статус",
  "adminAutopost.status.enabled": "Включено",
  "adminAutopost.status.disabled": "Выключено",
  "adminAutopost.status.channel": "Канал",
  "adminAutopost.status.notSet": "Не задан",
  "adminAutopost.status.channelLang": "Язык канала",
  "adminAutopost.status.minSalary": "Мин. зарплата",
  "adminAutopost.status.perDay": "Постов в день",
  "adminAutopost.status.perDayRange": "{min}–{max}",
  "adminAutopost.status.editLink": "Редактировать в настройках",
  "adminAutopost.status.sent": "Отправлено",
  "adminAutopost.status.failed": "Ошибка",
  "adminAutopost.status.skipped": "Пропущено",

  "adminAutopost.schedule.postedOf": "Опубликовано: {posted} / {total}",
  "adminAutopost.schedule.empty": "На сегодня слотов нет",

  "adminAutopost.postNow.title": "Опубликовать сейчас",
  "adminAutopost.postNow.description": "Введите UID вакансии или оставьте пустым — будет выбрана следующая подходящая вакансия.",
  "adminAutopost.postNow.uidLabel": "UID вакансии",
  "adminAutopost.postNow.uidPlaceholder": "osonish_12345",
  "adminAutopost.postNow.button": "Опубликовать сейчас",
  "adminAutopost.postNow.confirmTitle": "Подтвердите немедленную публикацию",
  "adminAutopost.postNow.confirmDescription": "{uid} будет опубликован в канале прямо сейчас. Продолжить?",
  "adminAutopost.postNow.confirmButton": "Опубликовать",
  "adminAutopost.postNow.nextInQueue": "Следующая подходящая вакансия",
  "adminAutopost.postNow.jobDone": "Вакансия опубликована в канале",
  "adminAutopost.postNow.jobFailedGeneric": "Публикация не удалась",
  "adminAutopost.postNow.jobStatus.queued": "В очереди",
  "adminAutopost.postNow.jobStatus.running": "Выполняется",
  "adminAutopost.postNow.jobStatus.done": "Готово",
  "adminAutopost.postNow.jobStatus.failed": "Ошибка",
  "adminAutopost.postNow.jobStatusLabel": "Статус задачи",
  "adminAutopost.postNow.resultUid": "Вакансия",
  "adminAutopost.postNow.resultMessageId": "ID сообщения",
  "adminAutopost.postNow.resultError": "Ошибка",

  "adminAutopost.history.title": "История публикаций",
  "adminAutopost.history.empty": "Публикаций пока нет",
  "adminAutopost.history.filter.status": "По статусу",
};

export default adminAutopost;
