import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminKeys, createContentCategory, deleteContentCategory, updateContentCategory } from "../../../api/admin";
import type { ContentCategory } from "../../../api/adminTypes";
import Field, { INPUT_CLS } from "../../../components/ui/Field";
import { useT } from "../../../i18n/useT";
import { useToast } from "../../../hooks/useToast";
import type { Lang } from "../../../store/lang";
import { mapContentError } from "./errorMapping";
import EditorShell from "./EditorShell";
import LangTabs from "./LangTabs";
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
  name: LocalizedText;
};

function toForm(category: ContentCategory | null): FormState {
  if (!category) return { id: "", sort_order: 0, name: emptyLocalized() };
  return { id: category.id, sort_order: category.sort_order, name: category.name };
}

export type CategoryEditorProps = {
  mode: "create" | "edit";
  initial: ContentCategory | null;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
};

export default function CategoryEditor({ mode, initial, onClose, onSaved, onDeleted }: CategoryEditorProps) {
  const t = useT();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [snapshot] = useState(() => toForm(initial));
  const [form, setForm] = useState<FormState>(snapshot);
  const [activeLang, setActiveLang] = useState<Lang>("uz");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(snapshot), [form, snapshot]);
  const nameErrors = useMemo(
    () => validateLocalizedField(form.name, { requireUz: true, maxLen: FIELD_MAX_LEN.name }),
    [form.name],
  );
  const idInvalid = mode === "create" && form.id.length > 0 && !SLUG_RE.test(form.id);
  const canSave = (mode === "edit" || (form.id.length > 0 && !idInvalid)) && !hasAnyError(nameErrors);

  const setName = (lang: Lang, value: string) => {
    setForm((prev) => ({ ...prev, name: setLocalizedValue(prev.name, lang, value) }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[`name.${lang}`];
      return next;
    });
  };

  const copyFromUz = () => setForm((prev) => ({ ...prev, name: setLocalizedValue(prev.name, activeLang, prev.name.uz) }));

  const saveMutation = useMutation({
    mutationFn: async () => {
      const body = { sort_order: form.sort_order, name: form.name };
      return mode === "create" ? createContentCategory({ ...body, id: form.id }) : updateContentCategory(initial!.id, body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.contentCategories() });
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
    mutationFn: () => deleteContentCategory(initial!.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.contentCategories() });
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
      title={mode === "create" ? t("adminContent.editor.newCategoryTitle") : form.id}
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
              placeholder="masalan-mehnat-huquqi"
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

      <div className="card space-y-3 p-4">
        <LangTabs
          value={activeLang}
          onChange={setActiveLang}
          filled={localizedHasContent(form.name)}
          invalid={{
            uz: Boolean(nameErrors.uz),
            ru: Boolean(nameErrors.ru),
            en: Boolean(nameErrors.en),
          }}
          onCopyFromUz={copyFromUz}
        />
        <Field
          label={t("adminContent.editor.fieldName")}
          required
          error={fieldErrors[`name.${activeLang}`]}
        >
          <input
            className={INPUT_CLS}
            value={localizedValue(form.name, activeLang)}
            onChange={(event) => setName(activeLang, event.target.value)}
            maxLength={FIELD_MAX_LEN.name}
          />
        </Field>
        <p className="text-right text-[11px] text-muted">
          {localizedValue(form.name, activeLang).length}/{FIELD_MAX_LEN.name}
        </p>
      </div>
    </EditorShell>
  );
}
