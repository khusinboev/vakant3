import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminKeys, createContentTip, deleteContentTip, updateContentTip } from "../../../api/admin";
import type { ContentTipAdmin } from "../../../api/adminTypes";
import Field, { INPUT_CLS } from "../../../components/ui/Field";
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
  sort_order: number;
  published: boolean;
  title: LocalizedText;
  summary: LocalizedText;
  full_text: LocalizedText;
};

function toForm(tip: ContentTipAdmin | null): FormState {
  if (!tip) {
    return {
      id: "",
      sort_order: 0,
      published: true,
      title: emptyLocalized(),
      summary: emptyLocalized(),
      full_text: emptyLocalized(),
    };
  }
  return {
    id: tip.id,
    sort_order: tip.sort_order,
    published: tip.published,
    title: tip.title,
    summary: tip.summary,
    full_text: tip.full_text,
  };
}

export type TipEditorProps = {
  mode: "create" | "edit";
  initial: ContentTipAdmin | null;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
};

export default function TipEditor({ mode, initial, onClose, onSaved, onDeleted }: TipEditorProps) {
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

  const invalidByLang: Partial<Record<Lang, boolean>> = {
    uz: Boolean(titleErrors.uz || summaryErrors.uz || fullTextErrors.uz),
    ru: Boolean(titleErrors.ru || summaryErrors.ru || fullTextErrors.ru),
    en: Boolean(titleErrors.en || summaryErrors.en || fullTextErrors.en),
  };
  const idInvalid = mode === "create" && form.id.length > 0 && !SLUG_RE.test(form.id);
  const canSave =
    (mode === "edit" || (form.id.length > 0 && !idInvalid)) &&
    !hasAnyError(titleErrors) &&
    !hasAnyError(summaryErrors) &&
    !hasAnyError(fullTextErrors);

  const setField = (field: "title" | "summary" | "full_text", lang: Lang, value: string) => {
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
    }));
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = {
        sort_order: form.sort_order,
        published: form.published,
        title: form.title,
        summary: form.summary,
        full_text: form.full_text,
      };
      return mode === "create" ? createContentTip({ ...body, id: form.id }) : updateContentTip(initial!.id, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.contentTips() });
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
    mutationFn: () => deleteContentTip(initial!.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.contentTips() });
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
      title={mode === "create" ? t("adminContent.editor.newTipTitle") : form.id}
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
              placeholder="masalan-shu-nomdagi-maslahat"
              autoComplete="off"
              spellCheck={false}
            />
          </Field>
        ) : (
          <Field label={t("adminContent.editor.idLabel")}>
            <input className={`${INPUT_CLS} opacity-60`} value={form.id} disabled />
          </Field>
        )}

        <Field label={t("adminContent.editor.sortOrderLabel")}>
          <input
            type="number"
            className={INPUT_CLS}
            value={form.sort_order}
            onChange={(event) => setForm((prev) => ({ ...prev, sort_order: Number(event.target.value) || 0 }))}
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
      </div>
    </EditorShell>
  );
}
