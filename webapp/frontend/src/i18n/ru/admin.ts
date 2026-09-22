import type { AdminDict } from "../uz/admin";

const admin: Record<keyof AdminDict, string> = {
  // ── Shell ──────────────────────────────────────────────────────────────────
  "admin.title": "Админ-панель",
  "admin.accessDenied": "Админ-панель доступна только администраторам.",


  "admin.status.on": "Включено",
  "admin.status.off": "Выключено",

  "admin.dash.sparklineAria": "График новых пользователей за последние 7 дней",
  "admin.dash.sparklineLabel": "Новые пользователи — 7 дней",
  "admin.dash.systemOk": "Система в порядке",
  "admin.dash.systemDegraded": "Проблема с системой",
  "admin.dash.systemUnknown": "Статус системы неизвестен",
  "admin.dash.autoPostLabel": "Авто-пост",
  "admin.dash.postedTodayLabel": "Опубликовано сегодня",
  "admin.dash.referralLabel": "Реферал",
  "admin.dash.minReferralsLabel": "Мин. рефералов",

  // ── Overview ───────────────────────────────────────────────────────────────
  "admin.overview.kpiTitle": "KPI-цели резюме",

  "admin.kpi.completion": "Завершение",
  "admin.kpi.sendSuccess": "Успешная отправка",
  "admin.kpi.pdfExport": "Экспорт PDF",
  "admin.kpi.creationTime": "Время создания",
  "admin.kpi.minutesShort": "мин",
  "admin.kpi.openedUsers": "Открыли",
  "admin.kpi.completedUsers": "Завершили",
  "admin.kpi.sendAttempts": "Отправили",

  // ── Settings ───────────────────────────────────────────────────────────────
  "admin.settings.group.autoPost": "Автопостинг",
  "admin.settings.group.referralGate": "Реферальное условие",
  "admin.settings.group.pro": "Тариф Pro",
  "admin.settings.group.resumeKpi": "KPI-цели резюме",

  "admin.settings.field.enabled": "Включено",
  "admin.settings.field.channel": "Канал",
  "admin.settings.field.channelLang": "Язык канала",
  "admin.settings.field.autoPostMinSalary": "Минимальная зарплата (сум)",
  "admin.settings.field.perDayMin": "Минимум в день",
  "admin.settings.field.perDayMax": "Максимум в день",
  "admin.settings.field.requiredRefs": "Требуется рефералов",
  "admin.settings.field.proPrice": "Цена Pro (сум)",
  "admin.settings.field.referralReward": "Награда за реферала (сум)",
  "admin.settings.field.proMinSalary": "Минимальная зарплата для Pro (сум)",
  "admin.settings.field.targetCreationMinutes": "Время создания (мин)",
  "admin.settings.field.targetCompletionRate": "Доля завершения (%)",
  "admin.settings.field.targetSendRate": "Успешная отправка (%)",
  "admin.settings.field.targetExportRate": "Успешный экспорт PDF (%)",

  "admin.settings.editAria": "{label} — изменить",
  "admin.settings.saved": "Настройка сохранена.",
  "admin.settings.saving": "Сохранение…",
  "admin.settings.conflict.message": "Настройка была изменена в другом месте.",
  "admin.settings.conflict.reload": "Обновить",
  "admin.settings.validation.number": "{label}: введите число.",
  "admin.settings.validation.negative": "{label}: не может быть отрицательным.",
  "admin.settings.validation.empty": "{label}: значение не может быть пустым.",
  "admin.settings.validation.perDayRange":
    "Минимум в день не должен превышать максимум ({min} > {max}).",

  // ── Analytics ──────────────────────────────────────────────────────────────
  "admin.analytics.opsTitle": "Операции (24 часа)",
  "admin.analytics.success": "Успешно",
  "admin.analytics.error": "Ошибка",
  "admin.analytics.opSave": "Сохранение",
  "admin.analytics.opSend": "Отправка",
  "admin.analytics.opExport": "Экспорт",
  "admin.analytics.activeUsers": "Активных пользователей",
  "admin.analytics.opened": "Открыто",
  "admin.analytics.ready": "Готово",
  "admin.analytics.latencyTitle": "Задержка (в среднем)",
  "admin.analytics.funnelTitle": "Воронка ({hours} ч)",
  "admin.analytics.funnelEmpty": "Данных по воронке нет.",
  "admin.analytics.diagTitle": "Ошибки диагностики",
  "admin.analytics.diagCount": "{n} раз",
  "admin.analytics.noErrors": "За последние 24 часа ошибок не найдено.",

  "admin.latency.ttfi": "TTFI",
  "admin.latency.save": "Сохранение",
  "admin.latency.send": "Отправка",
  "admin.latency.export": "Экспорт",
  "admin.latency.unit": "мс",

  "admin.funnel.entered": "{n} вошли",
  "admin.funnel.dropped": "{n} ушли",
  "admin.funnel.step.basic": "Основные данные",
  "admin.funnel.step.experience": "Опыт",
  "admin.funnel.step.education": "Образование",
  "admin.funnel.step.skills": "Навыки",
  "admin.funnel.step.summary": "О себе",
  "admin.funnel.step.template": "Шаблон",
  "admin.funnel.step.final": "Финал",

  // ── Users ──────────────────────────────────────────────────────────────────

  // ── Shell v2 (AdminLayout / registry / shared components) ─────────────────
  "admin.nav.aria": "Разделы админ-панели",
  "admin.nav.group.main": "Главное",
  "admin.nav.group.people": "Пользователи",
  "admin.nav.group.content": "Контент и каналы",
  "admin.nav.group.money": "Финансы",
  "admin.nav.group.system": "Система",

  "admin.nav.overview": "Панель",
  "admin.nav.analytics": "Аналитика",
  "admin.nav.resume": "Аналитика резюме",
  "admin.nav.users": "Пользователи",
  "admin.nav.broadcasts": "Рассылки",
  "admin.nav.channels": "Каналы",
  "admin.nav.autopost": "Автопостинг",
  "admin.nav.content": "Контент",
  "admin.nav.finance": "Финансы",
  "admin.nav.system": "Система",
  "admin.nav.settings": "Настройки",

  "admin.role.owner": "Владелец",
  "admin.role.admin": "Администратор",
  "admin.role.moderator": "Модератор",
  "admin.role.viewer": "Наблюдатель",
  "admin.role.required": "Для этого раздела нужна роль не ниже «{role}».",

  "admin.shell.openPanel": "Открыть админ-панель",

  "admin.table.empty": "Данных нет.",
  "admin.table.loadMore": "Показать ещё",
  "admin.table.loadingMore": "Загрузка...",
  "admin.table.total": "Всего: {total}",

  "admin.confirm.title": "Подтвердить действие?",
  "admin.confirm.confirm": "Подтвердить",
  "admin.confirm.cancel": "Отмена",
  "admin.confirm.working": "Выполняется...",

  "admin.filter.searchPlaceholder": "Поиск...",
  "admin.filter.all": "Все",
  "admin.filter.from": "С даты",
  "admin.filter.to": "По дату",

  "admin.empty.default": "Пока ничего нет.",
  "admin.stat.deltaUp": "рост на {value}",
  "admin.stat.deltaDown": "снижение на {value}",


  // ── Analytics dashboard (daily_stats rollup) ────────────────────────────────
  "admin.analytics2.stat.groupLabel": "Показатели за сегодня",
  "admin.analytics2.stat.hintToday": "сегодня",
  "admin.analytics2.stat.newUsers": "Новые пользователи",
  "admin.analytics2.stat.activeUsers": "Активные пользователи",
  "admin.analytics2.stat.proUsers": "Pro-пользователи",
  "admin.analytics2.stat.revenue": "Доход",
  "admin.analytics2.stat.saves": "Сохранения",
  "admin.analytics2.stat.resumeSendsOk": "Резюме отправлено",
  "admin.analytics2.stat.resumeSendsErr": "Ошибки резюме",
  "admin.analytics2.stat.autoPosts": "Авто-посты",
  "admin.analytics2.stat.notifications": "Уведомления",

  "admin.analytics2.chart.usersTitle": "Пользователи",
  "admin.analytics2.chart.usersAria": "График новых и активных пользователей по дням",
  "admin.analytics2.chart.usersNew": "Новые",
  "admin.analytics2.chart.usersActive": "Активные",
  "admin.analytics2.chart.revenueTitle": "Доход",
  "admin.analytics2.chart.revenueAria": "График дохода по дням",
  "admin.analytics2.chart.resumeSendsTitle": "Отправка резюме",
  "admin.analytics2.chart.resumeSendsAria": "График успешных и неудачных отправок резюме по дням",
  "admin.analytics2.chart.resumeOk": "Успешно",
  "admin.analytics2.chart.resumeErr": "Ошибка",
  "admin.analytics2.chart.notifTitle": "Уведомления и авто-посты",
  "admin.analytics2.chart.notifAria": "График уведомлений и авто-постов по дням",
  "admin.analytics2.chart.notifNotifications": "Уведомления",
  "admin.analytics2.chart.notifAutoPosts": "Авто-посты",

  "admin.analytics2.empty.title": "Статистика ещё не рассчитана",
  "admin.analytics2.empty.description":
    "Ежедневный расчёт (rollup) ещё не запускался — графики появятся после завершения первого дня.",

  "admin.analytics2.resumeKpi.title": "KPI резюме",

  // ── Shell v3 (AdminShell / AdminBar / Rail / ui kit) ─────────────────────
  "admin.shell.back": "Назад",
  "admin.shell.menu": "Ещё действия",
  "admin.shell.actions": "Действия",
  "admin.shell.content": "Содержимое админки",

  "admin.bar.home": "Главная",
  "admin.bar.users": "Люди",
  "admin.bar.broadcasts": "Рассылка",
  "admin.bar.more": "Ещё",

  "admin.more.title": "Разделы",
  "admin.more.quickActions": "Быстрые действия",
  "admin.more.quick.postNow": "Опубликовать сейчас",
  "admin.more.quick.newBroadcast": "Новая рассылка",
  "admin.more.quick.addChannel": "Добавить канал",

  "admin.rail.pin": "Закрепить меню",
  "admin.rail.unpin": "Свернуть меню",

  "admin.sheet.close": "Закрыть",

  "admin.filter.title": "Фильтры",
  "admin.filter.open": "Фильтры",
  "admin.filter.openCount": "Фильтры ({count})",
  "admin.filter.apply": "Применить",
  "admin.filter.clear": "Сбросить",
  "admin.filter.removeAria": "Убрать фильтр «{label}»",
  "admin.filter.on": "Включён",

  "admin.search.clear": "Очистить поиск",

  "admin.tabs.aria": "Разделы",
  "admin.toolbar.more": "Ещё",
  "admin.toolbar.moreAria": "Дополнительные действия",

  "admin.period.aria": "Период",
  "admin.period.7": "7 дней",
  "admin.period.30": "30 дней",
  "admin.period.90": "90 дней",
  "admin.period.365": "1 год",


};
export default admin;
