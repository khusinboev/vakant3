import type { AdminChannelsDict } from "../uz/adminChannels";

const adminChannels: Record<keyof AdminChannelsDict, string> = {
  "adminChannels.title": "Каналы",
  "adminChannels.subtitle":
    "Каналы, на которые пользователь обязан подписаться, прежде чем попасть в приложение.",

  "adminChannels.info.title": "Как работает вход в приложение",
  "adminChannels.info.step.start": "Старт бота",
  "adminChannels.info.step.subscribe": "Подписка",
  "adminChannels.info.step.referral": "Реферал",
  "adminChannels.info.description": "Включение и порог реферального условия",
  "adminChannels.info.settingsLink": "настраиваются на странице «Настройки»",

  "adminChannels.add.title": "Добавить канал",
  "adminChannels.add.linkLabel": "Ссылка на канал",
  "adminChannels.add.linkHint": "@имя, t.me/имя, t.me/+приглашение или -100 ID",
  "adminChannels.add.linkPlaceholder": "@мой_канал",
  "adminChannels.add.chatIdLabel": "Chat ID",
  "adminChannels.add.chatIdHint": "Для закрытых пригласительных ссылок нужен числовой ID",
  "adminChannels.add.checking": "Проверка...",
  "adminChannels.add.submit": "Добавить",
  "adminChannels.add.success.admin": "Бот — администратор этого канала ✓",
  "adminChannels.add.error.empty": "Ссылка не введена.",
  "adminChannels.add.error.badFormat": "Неверный формат ссылки. Введите @имя, t.me/имя или -100 ID.",
  "adminChannels.add.error.needsChatId": "Это закрытая пригласительная ссылка — укажите ниже chat ID.",
  "adminChannels.add.error.notFound": "Такой канал не найден.",
  "adminChannels.add.error.notAdmin": "Бот не администратор в этом канале. Добавьте бота администратором.",
  "adminChannels.add.error.notAdminNamed":
    "Бот не администратор в канале «{title}». Добавьте бота администратором.",
  "adminChannels.add.error.exists": "Этот канал уже добавлен ({id}).",
  "adminChannels.add.error.upstream": "Не удалось связаться с Telegram. Повторите попытку чуть позже.",
  "adminChannels.add.error.generic": "Не удалось добавить канал. Попробуйте ещё раз.",

  "adminChannels.table.caption": "Каналы обязательной подписки",
  "adminChannels.column.channel": "Канал",
  "adminChannels.column.status": "Статус",
  "adminChannels.column.enabled": "Включён",
  "adminChannels.column.actions": "Действия",
  "adminChannels.status.never": "Ещё не проверялся",
  "adminChannels.status.ok": "ОК — {time}",
  "adminChannels.status.failed": "Есть проблема — {time}",
  "adminChannels.status.enabled": "Включён",
  "adminChannels.status.disabled": "Отключён",
  "adminChannels.action.check": "{name} — проверить сейчас",
  "adminChannels.action.delete": "{name} — удалить",
  "adminChannels.check.ok": "Всё в порядке — бот администратор.",
  "adminChannels.check.failed": "Обнаружена проблема. Посмотрите статус в списке.",
  "adminChannels.empty": "Каналы ещё не добавлены.",

  "adminChannels.delete.title": "Удалить канал?",
  "adminChannels.delete.description":
    "«{name}» будет удалён из условия входа. Это действие нельзя отменить.",
  "adminChannels.delete.success": "Канал удалён.",
};
export default adminChannels;
