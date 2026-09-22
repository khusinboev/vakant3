import {
  adminKeys,
  createContentArticle,
  createContentCategory,
  createContentTip,
  deleteContentArticle,
  deleteContentCategory,
  deleteContentTip,
  listContentArticles,
  listContentCategories,
  listContentTips,
  updateContentArticle,
  updateContentCategory,
  updateContentTip,
} from "../../../api/admin";
import type { LocalizedText } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import { FIELD_MAX_LEN } from "./richtext";
import { emptyLocalized } from "./types";

/** The three entity kinds behind `/admin/content/:kind`. */
export type ContentKind = "articles" | "tips" | "categories";

export const CONTENT_KINDS: ContentKind[] = ["articles", "tips", "categories"];

export const DEFAULT_CONTENT_KIND: ContentKind = "articles";

export function isContentKind(value: string | undefined): value is ContentKind {
  return value === "articles" || value === "tips" || value === "categories";
}

/**
 * The structural supertype of `ContentArticleAdmin | ContentTipAdmin |
 * ContentCategory`: the list and the editor are one screen each, so they read
 * every kind through the same shape and let `KindConfig` say which parts exist.
 */
export type ContentRecord = {
  id: string;
  sort_order: number;
  published?: boolean;
  category_id?: string;
  title?: LocalizedText;
  name?: LocalizedText;
  summary?: LocalizedText;
  full_text?: LocalizedText;
  source_url?: string;
  source_label?: LocalizedText;
};

/** One editor form for all three kinds; unused parts stay empty. */
export type ContentForm = {
  id: string;
  category_id: string;
  sort_order: number;
  published: boolean;
  source_url: string;
  /** Articles/tips: `title`. Categories: `name` (same field, renamed on save). */
  title: LocalizedText;
  summary: LocalizedText;
  full_text: LocalizedText;
  source_label: LocalizedText;
};

export type KindConfig = {
  kind: ContentKind;
  tabLabelKey: TranslationKey;
  newLabelKey: TranslationKey;
  newTitleKey: TranslationKey;
  emptyKey: TranslationKey;
  /** The server field the localized "title" maps to (`name` for categories). */
  titleField: "title" | "name";
  titleLabelKey: TranslationKey;
  titleSectionKey: TranslationKey;
  titleMaxLen: number;
  idPlaceholder: string;
  hasCategory: boolean;
  hasPublished: boolean;
  /** Summary + full text (articles and tips). */
  hasBody: boolean;
  hasSource: boolean;
  queryKey: () => readonly unknown[];
  list: () => Promise<{ items: ContentRecord[] }>;
  remove: (id: string) => Promise<unknown>;
};

export const CONTENT_CONFIG: Record<ContentKind, KindConfig> = {
  articles: {
    kind: "articles",
    tabLabelKey: "adminContent.tab.articles",
    newLabelKey: "adminContent.new.article",
    newTitleKey: "adminContent.editor.newArticleTitle",
    emptyKey: "adminContent.empty.articles",
    titleField: "title",
    titleLabelKey: "adminContent.editor.fieldTitle",
    titleSectionKey: "adminContent.section.titles",
    titleMaxLen: FIELD_MAX_LEN.title,
    idPlaceholder: "mehnat-shartnomasi",
    hasCategory: true,
    hasPublished: true,
    hasBody: true,
    hasSource: true,
    queryKey: adminKeys.contentArticles,
    list: listContentArticles,
    remove: deleteContentArticle,
  },
  tips: {
    kind: "tips",
    tabLabelKey: "adminContent.tab.tips",
    newLabelKey: "adminContent.new.tip",
    newTitleKey: "adminContent.editor.newTipTitle",
    emptyKey: "adminContent.empty.tips",
    titleField: "title",
    titleLabelKey: "adminContent.editor.fieldTitle",
    titleSectionKey: "adminContent.section.titles",
    titleMaxLen: FIELD_MAX_LEN.title,
    idPlaceholder: "rezyume-maslahati",
    hasCategory: false,
    hasPublished: true,
    hasBody: true,
    hasSource: false,
    queryKey: adminKeys.contentTips,
    list: listContentTips,
    remove: deleteContentTip,
  },
  categories: {
    kind: "categories",
    tabLabelKey: "adminContent.tab.categories",
    newLabelKey: "adminContent.new.category",
    newTitleKey: "adminContent.editor.newCategoryTitle",
    emptyKey: "adminContent.empty.categories",
    titleField: "name",
    titleLabelKey: "adminContent.editor.fieldName",
    titleSectionKey: "adminContent.section.name",
    titleMaxLen: FIELD_MAX_LEN.name,
    idPlaceholder: "mehnat-huquqi",
    hasCategory: false,
    hasPublished: false,
    hasBody: false,
    hasSource: false,
    queryKey: adminKeys.contentCategories,
    list: listContentCategories,
    remove: deleteContentCategory,
  },
};

export function contentPath(kind: ContentKind, id?: string): string {
  return id ? `/admin/content/${kind}/${id}` : `/admin/content/${kind}`;
}

export function toForm(kind: ContentKind, record: ContentRecord | null): ContentForm {
  const config = CONTENT_CONFIG[kind];
  const title = (config.titleField === "name" ? record?.name : record?.title) ?? emptyLocalized();
  return {
    id: record?.id ?? "",
    category_id: record?.category_id ?? "",
    sort_order: record?.sort_order ?? 0,
    published: record?.published ?? true,
    source_url: record?.source_url ?? "",
    title,
    summary: record?.summary ?? emptyLocalized(),
    full_text: record?.full_text ?? emptyLocalized(),
    source_label: record?.source_label ?? emptyLocalized(),
  };
}

/** Create (`id === null`) or update one record, with only the kind's own fields. */
export function saveRecord(kind: ContentKind, id: string | null, form: ContentForm): Promise<unknown> {
  if (kind === "articles") {
    const body = {
      category_id: form.category_id,
      sort_order: form.sort_order,
      published: form.published,
      source_url: form.source_url,
      title: form.title,
      summary: form.summary,
      full_text: form.full_text,
      source_label: form.source_label,
    };
    return id ? updateContentArticle(id, body) : createContentArticle({ ...body, id: form.id });
  }
  if (kind === "tips") {
    const body = {
      sort_order: form.sort_order,
      published: form.published,
      title: form.title,
      summary: form.summary,
      full_text: form.full_text,
    };
    return id ? updateContentTip(id, body) : createContentTip({ ...body, id: form.id });
  }
  const body = { sort_order: form.sort_order, name: form.title };
  return id ? updateContentCategory(id, body) : createContentCategory({ ...body, id: form.id });
}
