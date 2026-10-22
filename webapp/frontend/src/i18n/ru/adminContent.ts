import type { AdminContentDict } from "../uz/adminContent";

const adminContent: Record<keyof AdminContentDict, string> = {
  "adminContent.tabs.aria": "Разделы контента",
  "adminContent.tab.articles": "Статьи",
  "adminContent.tab.tips": "Советы",
  "adminContent.tab.categories": "Категории",

  "adminContent.list.searchPlaceholder": "Поиск по ID или заголовку",
  "adminContent.list.category": "Категория",
  "adminContent.list.published": "Опубликовано",
  "adminContent.list.unpublished": "Не опубликовано",
  "adminContent.list.sort": "Порядок",

  "adminContent.filter.yes": "Да",
  "adminContent.filter.no": "Нет",

  "adminContent.new.article": "Новая",
  "adminContent.new.tip": "Новый",
  "adminContent.new.category": "Новая",

  "adminContent.empty.articles": "Статей пока нет.",
  "adminContent.empty.tips": "Советов пока нет.",
  "adminContent.empty.categories": "Категорий пока нет.",

  "adminContent.section.basic": "Основное",
  "adminContent.section.titles": "Заголовок и краткое описание",
  "adminContent.section.name": "Название",
  "adminContent.section.body": "Текст",
  "adminContent.section.source": "Источник",

  "adminContent.editor.backToList": "Вернуться к списку",
  "adminContent.editor.unsavedBadge": "Есть несохранённые изменения",
  "adminContent.editor.save": "Сохранить",
  "adminContent.editor.delete": "Удалить",
  "adminContent.editor.deleteTitle": "Подтвердить удаление?",
  "adminContent.editor.deleteDesc": "«{id}» будет удалён безвозвратно. Отменить это действие нельзя.",
  "adminContent.editor.deleteConfirm": "Да, удалить",
  "adminContent.editor.discardTitle": "Есть несохранённые изменения",
  "adminContent.editor.discardDesc": "Если выйти сейчас, внесённые изменения будут потеряны.",
  "adminContent.editor.discardConfirm": "Да, отменить",

  "adminContent.editor.newArticleTitle": "Новая статья",
  "adminContent.editor.newTipTitle": "Новый совет",
  "adminContent.editor.newCategoryTitle": "Новая категория",

  "adminContent.editor.idLabel": "ID (slug)",
  "adminContent.editor.idHint": "только латиница, цифры и дефис, 3–60 символов",
  "adminContent.editor.idInvalid": "ID может содержать только строчные латинские буквы, цифры и «-» (3–60 символов).",
  "adminContent.editor.categoryLabel": "Категория",
  "adminContent.editor.categoryPlaceholder": "Выберите категорию",
  "adminContent.editor.sortOrderLabel": "Порядковый номер",
  "adminContent.editor.sourceUrlLabel": "Ссылка на источник",
  "adminContent.editor.optionalHint": "(необязательно)",
  "adminContent.editor.publishedLabel": "Опубликовано",
  "adminContent.editor.langTabs": "Язык",
  "adminContent.editor.copyFromUz": "Скопировать с узбекского",

  "adminContent.editor.created": "Создано.",
  "adminContent.editor.saved": "Сохранено.",
  "adminContent.editor.deleted": "Удалено.",

  "adminContent.editor.fieldTitle": "Заголовок",
  "adminContent.editor.fieldSummary": "Краткое описание",
  "adminContent.editor.fieldFullText": "Полный текст",
  "adminContent.editor.fieldSourceLabel": "Название источника",
  "adminContent.editor.fieldName": "Название",

  "adminContent.toolbar.aria": "Панель форматирования",
  "adminContent.toolbar.bold": "Жирный",
  "adminContent.toolbar.italic": "Курсив",
  "adminContent.toolbar.underline": "Подчёркнутый",
  "adminContent.toolbar.code": "Код",
  "adminContent.toolbar.link": "Ссылка",
  "adminContent.toolbar.br": "Перенос строки",
  "adminContent.toolbar.showPreview": "Предпросмотр",
  "adminContent.toolbar.hidePreview": "Вернуться к редактированию",
  "adminContent.toolbar.invalidHtml": "Недопустимая разметка: разрешены только <b> <i> <u> <a href> <code> <br>.",
  "adminContent.toolbar.linkPrompt": "Адрес ссылки (https://...)",
  "adminContent.toolbar.linkSample": "текст ссылки",
  "adminContent.toolbar.sample": "текст",

  "adminContent.error.validation": "Поле заполнено неверно или слишком длинное.",
  "adminContent.error.exists": "Этот ID занят. Выберите другой.",
  "adminContent.error.inUse": "В этой категории есть статьи — сначала перенесите или удалите их.",
  "adminContent.error.notFound": "Запись не найдена — список обновлён.",
};
export default adminContent;
