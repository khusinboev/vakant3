import type { AdminContentDict } from "../uz/adminContent";

const adminContent: Record<keyof AdminContentDict, string> = {
  "adminContent.tabs.aria": "Content sections",
  "adminContent.tab.articles": "Articles",
  "adminContent.tab.tips": "Tips",
  "adminContent.tab.categories": "Categories",

  "adminContent.list.searchPlaceholder": "Search by ID or title",
  "adminContent.list.category": "Category",
  "adminContent.list.published": "Published",
  "adminContent.list.unpublished": "Unpublished",
  "adminContent.list.sort": "Order",

  "adminContent.filter.yes": "Yes",
  "adminContent.filter.no": "No",

  "adminContent.new.article": "New",
  "adminContent.new.tip": "New",
  "adminContent.new.category": "New",

  "adminContent.empty.articles": "No articles yet.",
  "adminContent.empty.tips": "No tips yet.",
  "adminContent.empty.categories": "No categories yet.",

  "adminContent.section.basic": "Basics",
  "adminContent.section.titles": "Title and summary",
  "adminContent.section.name": "Name",
  "adminContent.section.body": "Text",
  "adminContent.section.source": "Source",

  "adminContent.editor.backToList": "Back to the list",
  "adminContent.editor.unsavedBadge": "Unsaved changes",
  "adminContent.editor.save": "Save",
  "adminContent.editor.delete": "Delete",
  "adminContent.editor.deleteTitle": "Confirm deletion?",
  "adminContent.editor.deleteDesc": "\"{id}\" will be deleted permanently. This cannot be undone.",
  "adminContent.editor.deleteConfirm": "Yes, delete",
  "adminContent.editor.discardTitle": "You have unsaved changes",
  "adminContent.editor.discardDesc": "If you leave now, your edits will be lost.",
  "adminContent.editor.discardConfirm": "Yes, discard",

  "adminContent.editor.newArticleTitle": "New article",
  "adminContent.editor.newTipTitle": "New tip",
  "adminContent.editor.newCategoryTitle": "New category",

  "adminContent.editor.idLabel": "ID (slug)",
  "adminContent.editor.idHint": "latin letters, digits and hyphens only, 3–60 characters",
  "adminContent.editor.idInvalid": "The ID may contain only lowercase latin letters, digits and \"-\" (3–60 characters).",
  "adminContent.editor.categoryLabel": "Category",
  "adminContent.editor.categoryPlaceholder": "Choose a category",
  "adminContent.editor.sortOrderLabel": "Sort order",
  "adminContent.editor.sourceUrlLabel": "Source link",
  "adminContent.editor.optionalHint": "(optional)",
  "adminContent.editor.publishedLabel": "Published",
  "adminContent.editor.langTabs": "Language",
  "adminContent.editor.copyFromUz": "Copy from Uzbek",

  "adminContent.editor.created": "Created.",
  "adminContent.editor.saved": "Saved.",
  "adminContent.editor.deleted": "Deleted.",

  "adminContent.editor.fieldTitle": "Title",
  "adminContent.editor.fieldSummary": "Summary",
  "adminContent.editor.fieldFullText": "Full text",
  "adminContent.editor.fieldSourceLabel": "Source label",
  "adminContent.editor.fieldName": "Name",

  "adminContent.toolbar.aria": "Formatting toolbar",
  "adminContent.toolbar.bold": "Bold",
  "adminContent.toolbar.italic": "Italic",
  "adminContent.toolbar.underline": "Underline",
  "adminContent.toolbar.code": "Code",
  "adminContent.toolbar.link": "Link",
  "adminContent.toolbar.br": "Line break",
  "adminContent.toolbar.showPreview": "Preview",
  "adminContent.toolbar.hidePreview": "Back to editing",
  "adminContent.toolbar.invalidHtml": "Markup not allowed: only <b> <i> <u> <a href> <code> <br>.",
  "adminContent.toolbar.linkPrompt": "Link address (https://...)",
  "adminContent.toolbar.linkSample": "link text",
  "adminContent.toolbar.sample": "text",

  "adminContent.error.validation": "This field is invalid or too long.",
  "adminContent.error.exists": "That ID is taken. Pick another one.",
  "adminContent.error.inUse": "This category still has articles — move or delete them first.",
  "adminContent.error.notFound": "Record not found — the list has been refreshed.",
};
export default adminContent;
