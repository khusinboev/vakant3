import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminKeys, createContentArticle, deleteContentArticle, updateContentArticle } from "../../../api/admin";
import type { ContentArticleAdmin, ContentCategory } from "../../../api/adminTypes";
import Field, { INPUT_CLS } from "../../../components/ui/Field";
import StyledSelect from "../../../components/ui/StyledSelect";
import { useT } from "../../../i18n/useT";
import { useToast } from "../../../hooks/useToast";
import type { Lang } from "../../../store/lang";
import ToggleRow from "../components/ToggleRow";
import { mapContentError } from "./errorMapping";
import EditorShell from "./EditorShell";
import LangTabs from "./LangTabs";
import RichTextField from "./RichTextField";
import { FIELD_MAX_LEN, SLUG_RE } from "./richtext";
import {
  emptyLocalized,
  hasAnyError,
  localizedHasContent,
  localizedValue,
  setLocalizedValue,
  validateLocalizedField,
  type LocalizedText,
} from "./types";

type FormState = {
  id: string;
  category_id: string;
  sort_order: number;
  published: boolean;
  source_url: string;
  title: LocalizedText;
  summary: LocalizedText;
  full_text: LocalizedText;
  source_label: LocalizedText;
};

function toForm(article: ContentArticleAdmin | null): FormState {
  if (!article) {
    return {
      id: "",
      category_id: "",
      sort_order: 0,
      published: true,
      source_url: "",
      title: emptyLocalized(),
      summary: emptyLocalized(),
      full_text: emptyLocalized(),
      source_label: emptyLocalized(),
    };
  }
  return {
    id: article.id,
    category_id: article.category_id,
    sort_order: article.sort_order,
    published: article.published,
    source_url: article.source_url ?? "",
    title: article.title,
    summary: article.summary,
    full_text: article.full_text,
    source_label: article.source_label,
  };
}

export type ArticleEditorProps = {
  mode: "create" | "edit";
  initial: ContentArticleAdmin | null;
  categories: ContentCategory[];
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
};

export default function ArticleEditor({ mode, initial, categories, onClose, onSaved, onDeleted }: ArticleEditorProps) {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [snapshot] = useState(() => toForm(initial));
  const [form, setForm] = useState<FormState>(snapshot);
  const [activeLang, setActiveLang] = useState<Lang>("uz");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(snapshot), [form, snapshot]);

  const titleErrors = useMemo(() => validateLocalizedField(form.title, { requireUz: true, maxLen: FIELD_MAX_LEN.title }), [form.title]);
  const summaryErrors = useMemo(() => validateLocalizedField(form.summary, { requireUz: true, maxLen: FIELD_MAX_LEN.summary }), [form.summary]);
  const fullTextErrors = useMemo(() => validateLocalizedField(form.full_text, { requireUz: true, maxLen: FIELD_MAX_LEN.full_text }), [form.full_text]);
  const sourceLabelErrors = useMemo(() => validateLocalizedField(form.source_label, { requireUz: false, maxLen: FIELD_MAX_LEN.source_label }), [form.source_label]);

  const invalidByLang: Partial<Record<Lang, boolean>> = {
    uz: Boolean(titleErrors.uz || summaryErrors.uz || fullTextErrors.uz || sourceLabelErrors.uz),
    ru: Boolean(titleErrors.ru || summaryErrors.ru || fullTextErrors.ru || sourceLabelErrors.ru),
    en: Boolean(titleErrors.en || summaryErrors.en || fullTextErrors.en || sourceLabelErrors.en),
  };
  const idInvalid = mode === "create" && form.id.length > 0 && !SLUG_RE.test(form.id);
  const canSave =
    (mode === "edit" || (form.id.length > 0 && !idInvalid)) &&
    form.category_id.length > 0 &&
    !hasAnyError(titleErrors) &&
    !hasAnyError(summaryErrors) &&
    !hasAnyError(fullTextErrors) &&
    !hasAnyError(sourceLabelErrors);

  const setField = (field: "title" | "summary" | "full_text" | "source_label", lang: Lang, value: string) => {
    setForm((prev) => ({ ...prev, [field]: setLocalizedValue(prev[field], lang, value) }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[`${field}.${lang}`];
      return next;
    });
  };

  const copyFromUz = () => {
    setForm((prev) => ({
      ...prev,
      title: setLocalizedValue(prev.title, activeLang, prev.title.uz),
      summary: setLocalizedValue(prev.summary, activeLang, prev.summary.uz),
      full_text: setLocalizedValue(prev.full_text, activeLang, prev.full_text.uz),
      source_label: setLocalizedValue(prev.source_label, activeLang, prev.source_label.uz),
    }));
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
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
      return mode === "create"
        ? createContentArticle({ ...body, id: form.id })
        : updateContentArticle(initial!.id, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.contentArticles() });
      toast.success(t(mode === "create" ? "adminContent.editor.created" : "adminContent.editor.saved"));
      onSaved();
    },
    onError: (error) => {
      const result = mapContentError(error, t);
      if (result.toastMessage) {
        toast.error(result.toastMessage);
      } else if (Object.keys(result.fieldErrors).length > 0) {
        setFieldErrors((prev) => ({ ...prev, ...result.fieldErrors }));
        const badField = Object.keys(result.fieldErrors).find((key) => key.includes("."));
        if (badField) setActiveLang(badField.split(".")[1] as Lang);
      } else {
        toast.apiError(error);
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteContentArticle(initial!.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.contentArticles() });
      toast.success(t("adminContent.editor.deleted"));
      onDeleted();
    },
    onError: (error) => {
      const result = mapContentError(error, t);
      toast.error(result.toastMessage ?? t("error.UNKNOWN"));
      if (result.unmapped) toast.apiError(error);
    },
  });

  return (
    <EditorShell
      title={mode === "create" ? t("adminContent.editor.newArticleTitle") : form.id}
      dirty={dirty}
      saving={saveMutation.isPending}
      onBack={onClose}
      onSave={() => saveMutation.mutate()}
      saveDisabled={!canSave}
      onDelete={mode === "edit" ? () => deleteMutation.mutate() : undefined}
      deleting={deleteMutation.isPending}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {mode === "create" ? (
          <Field
            label={t("adminContent.editor.idLabel")}
            required
            hint={t("adminContent.editor.idHint")}
            error={idInvalid ? t("adminContent.editor.idInvalid") : fieldErrors.id}
          >
            <input
              className={INPUT_CLS}
              value={form.id}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, id: event.target.value.trim().toLowerCase() }));
                setFieldErrors((prev) => ({ ...prev, id: "" }));
              }}
              placeholder="masalan-shu-nomdagi-maqola"
              autoComplete="off"
              spellCheck={false}
            />
          </Field>
        ) : (
          <Field label={t("adminContent.editor.idLabel")}>
            <input className={`${INPUT_CLS} opacity-60`} value={form.id} disabled />
          </Field>
        )}

        <Field label={t("adminContent.editor.categoryLabel")} required error={fieldErrors.category_id}>
          <StyledSelect
            value={form.category_id}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, category_id: event.target.value }));
              setFieldErrors((prev) => ({ ...prev, category_id: "" }));
            }}
            aria-label={t("adminContent.editor.categoryLabel")}
          >
            <option value="" disabled>
              {t("adminContent.editor.categoryPlaceholder")}
            </option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name.uz}
              </option>
            ))}
          </StyledSelect>
        </Field>

        <Field label={t("adminContent.editor.sortOrderLabel")}>
          <input
            type="number"
            className={INPUT_CLS}
            value={form.sort_order}
            onChange={(event) => setForm((prev) => ({ ...prev, sort_order: Number(event.target.value) || 0 }))}
          />
        </Field>

        <Field label={t("adminContent.editor.sourceUrlLabel")} hint={t("adminContent.editor.optionalHint")}>
          <input
            type="url"
            className={INPUT_CLS}
            value={form.source_url}
            onChange={(event) => setForm((prev) => ({ ...prev, source_url: event.target.value }))}
            placeholder="https://lex.uz/..."
          />
        </Field>
      </div>

      <div className="card p-3">
        <ToggleRow
          label={t("adminContent.editor.publishedLabel")}
          checked={form.published}
          onChange={(value) => setForm((prev) => ({ ...prev, published: value }))}
        />
      </div>

      <div className="card space-y-4 p-4">
        <LangTabs
          value={activeLang}
          onChange={setActiveLang}
          filled={localizedHasContent(form.title)}
          invalid={invalidByLang}
          onCopyFromUz={copyFromUz}
        />

        <RichTextField
          label={t("adminContent.editor.fieldTitle")}
          required
          value={localizedValue(form.title, activeLang)}
          onChange={(value) => setField("title", activeLang, value)}
          maxLen={FIELD_MAX_LEN.title}
          rows={2}
          errorText={fieldErrors[`title.${activeLang}`]}
        />
        <RichTextField
          label={t("adminContent.editor.fieldSummary")}
          required
          value={localizedValue(form.summary, activeLang)}
          onChange={(value) => setField("summary", activeLang, value)}
          maxLen={FIELD_MAX_LEN.summary}
          rows={3}
          errorText={fieldErrors[`summary.${activeLang}`]}
        />
        <RichTextField
          label={t("adminContent.editor.fieldFullText")}
          required
          value={localizedValue(form.full_text, activeLang)}
          onChange={(value) => setField("full_text", activeLang, value)}
          maxLen={FIELD_MAX_LEN.full_text}
          rows={10}
          errorText={fieldErrors[`full_text.${activeLang}`]}
        />
        <RichTextField
          label={t("adminContent.editor.fieldSourceLabel")}
          value={localizedValue(form.source_label, activeLang)}
          onChange={(value) => setField("source_label", activeLang, value)}
          maxLen={FIELD_MAX_LEN.source_label}
          rows={1}
          errorText={fieldErrors[`source_label.${activeLang}`]}
        />
      </div>
    </EditorShell>
  );
}
