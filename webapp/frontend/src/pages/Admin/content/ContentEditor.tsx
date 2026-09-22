import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { adminKeys } from "../../../api/admin";
import { clearBackInterceptor, setBackInterceptor } from "../../../hooks/useBackInterceptor";
import { useToast } from "../../../hooks/useToast";
import { useT } from "../../../i18n/useT";
import { LANGS, LANG_META, type Lang } from "../../../store/lang";
import ErrorCard from "../components/ErrorCard";
import ToggleRow from "../components/ToggleRow";
import { requestConfirm } from "../hooks/useConfirm";
import { useAdminHeader } from "../hooks/useAdminHeader";
import Accordion, { type AccordionItem } from "../ui/Accordion";
import Button from "../ui/Button";
import EmptyState from "../ui/EmptyState";
import Skeleton from "../ui/Skeleton";
import { SegmentedControl } from "../ui/Tabs";
import { mapContentError } from "./errorMapping";
import {
  CONTENT_CONFIG,
  contentPath,
  saveRecord,
  toForm,
  type ContentForm,
  type ContentKind,
  type ContentRecord,
} from "./kinds";
import RichTextField, { FIELD_INPUT } from "./RichTextField";
import { FIELD_MAX_LEN, SLUG_RE } from "./richtext";
import {
  hasAnyError,
  localizedValue,
  setLocalizedValue,
  validateLocalizedField,
  type FieldErrorKind,
} from "./types";
import { useContentCategories } from "./useContentCategories";

type LocalizedField = "title" | "summary" | "full_text" | "source_label";

function Labeled({
  label,
  required,
  hint,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1">
      <span className="block text-[11px] font-semibold text-muted">
        {label}
        {required && <span className="text-danger"> *</span>}
        {hint && <span className="ml-1 font-normal text-muted/80">{hint}</span>}
      </span>
      {children}
      {error && (
        <p role="alert" className="text-[11px] text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

function EditorForm({ kind, initial }: { kind: ContentKind; initial: ContentRecord | null }) {
  const t = useT();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const config = CONTENT_CONFIG[kind];
  const { categories } = useContentCategories();
  const mode = initial ? "edit" : "create";

  const [snapshot, setSnapshot] = useState<ContentForm>(() => toForm(kind, initial));
  const [form, setForm] = useState<ContentForm>(snapshot);
  const [activeLang, setActiveLang] = useState<Lang>("uz");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(snapshot), [form, snapshot]);
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;

  // ── Validation (mirrors admin_content.py) ────────────────────────────────
  const titleErrors = useMemo(
    () => validateLocalizedField(form.title, { requireUz: true, maxLen: config.titleMaxLen }),
    [form.title, config.titleMaxLen],
  );
  const summaryErrors = useMemo(
    () => validateLocalizedField(form.summary, { requireUz: config.hasBody, maxLen: FIELD_MAX_LEN.summary }),
    [form.summary, config.hasBody],
  );
  const fullTextErrors = useMemo(
    () => validateLocalizedField(form.full_text, { requireUz: config.hasBody, maxLen: FIELD_MAX_LEN.full_text }),
    [form.full_text, config.hasBody],
  );
  const sourceLabelErrors = useMemo(
    () => validateLocalizedField(form.source_label, { requireUz: false, maxLen: FIELD_MAX_LEN.source_label }),
    [form.source_label],
  );

  const activeErrors: Record<LocalizedField, Partial<Record<Lang, FieldErrorKind>>> = {
    title: titleErrors,
    summary: config.hasBody ? summaryErrors : {},
    full_text: config.hasBody ? fullTextErrors : {},
    source_label: config.hasSource ? sourceLabelErrors : {},
  };

  const invalidLang = (lang: Lang) =>
    Boolean(
      activeErrors.title[lang] ||
        activeErrors.summary[lang] ||
        activeErrors.full_text[lang] ||
        activeErrors.source_label[lang],
    );

  const idInvalid = mode === "create" && form.id.length > 0 && !SLUG_RE.test(form.id);
  const canSave =
    (mode === "edit" || (form.id.length > 0 && !idInvalid)) &&
    (!config.hasCategory || form.category_id.length > 0) &&
    !hasAnyError(activeErrors.title) &&
    !hasAnyError(activeErrors.summary) &&
    !hasAnyError(activeErrors.full_text) &&
    !hasAnyError(activeErrors.source_label);

  /** Articles/tips send `title`, categories send `name` — errors come back keyed the same way. */
  const serverKey = (field: LocalizedField) => (field === "title" ? config.titleField : field);

  const setField = (field: LocalizedField, lang: Lang, value: string) => {
    setForm((prev) => ({ ...prev, [field]: setLocalizedValue(prev[field], lang, value) }));
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[`${serverKey(field)}.${lang}`];
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

  // ── Navigation + unsaved-changes guard ───────────────────────────────────
  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: config.queryKey() });
    // Articles show their category's name, so a category change touches both.
    if (kind === "categories") void queryClient.invalidateQueries({ queryKey: adminKeys.contentArticles() });
  }, [config, kind, queryClient]);

  const leave = useCallback(() => {
    dirtyRef.current = false;
    clearBackInterceptor();
    const idx = (window.history.state as { idx?: number } | null)?.idx;
    if (typeof idx === "number" && idx > 0) navigate(-1);
    else navigate(contentPath(kind), { replace: true });
  }, [kind, navigate]);

  const handleBack = useCallback(async () => {
    if (dirtyRef.current) {
      const ok = await requestConfirm({
        titleKey: "adminContent.editor.discardTitle",
        descriptionKey: "adminContent.editor.discardDesc",
        confirmLabelKey: "adminContent.editor.discardConfirm",
        danger: true,
      });
      if (!ok) return;
    }
    leave();
  }, [leave]);

  // Telegram BackButton / browser back ask before throwing edits away; the
  // header ‹ and Esc go through `useAdminHeader({ back })` to the same place.
  useEffect(() => {
    if (dirty) setBackInterceptor(() => {
      void handleBack();
      return true;
    });
    else clearBackInterceptor();
    return () => clearBackInterceptor();
  }, [dirty, handleBack]);

  // ── Mutations ────────────────────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: () => saveRecord(kind, initial ? initial.id : null, form),
    onSuccess: () => {
      invalidate();
      setSnapshot(form);
      dirtyRef.current = false;
      clearBackInterceptor();
      toast.success(t(mode === "create" ? "adminContent.editor.created" : "adminContent.editor.saved"));
      navigate(contentPath(kind), { replace: true });
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
    mutationFn: () => config.remove(initial!.id),
    onSuccess: () => {
      invalidate();
      toast.success(t("adminContent.editor.deleted"));
      leave();
    },
    onError: (error) => {
      const result = mapContentError(error, t);
      if (result.toastMessage) toast.error(result.toastMessage);
      else toast.apiError(error);
    },
  });

  const handleDelete = async () => {
    if (!initial) return;
    const ok = await requestConfirm({
      titleKey: "adminContent.editor.deleteTitle",
      descriptionKey: "adminContent.editor.deleteDesc",
      descriptionVars: { id: initial.id },
      confirmLabelKey: "adminContent.editor.deleteConfirm",
      danger: true,
    });
    if (ok) deleteMutation.mutate();
  };

  useAdminHeader({
    title: mode === "create" ? t(config.newTitleKey) : form.id,
    back: () => void handleBack(),
    primary: {
      labelKey: "adminContent.editor.save",
      onClick: () => saveMutation.mutate(),
      disabled: !canSave,
      loading: saveMutation.isPending,
    },
    menu: [
      {
        labelKey: "adminContent.editor.copyFromUz",
        onClick: copyFromUz,
        hidden: activeLang === "uz",
      },
      {
        labelKey: "adminContent.editor.delete",
        onClick: () => void handleDelete(),
        danger: true,
        hidden: mode === "create",
        disabled: deleteMutation.isPending,
      },
    ],
  });

  // ── Sections ─────────────────────────────────────────────────────────────
  const basic = (
    <div className="space-y-2">
      <Labeled
        label={t("adminContent.editor.idLabel")}
        required={mode === "create"}
        hint={mode === "create" ? t("adminContent.editor.idHint") : undefined}
        error={idInvalid ? t("adminContent.editor.idInvalid") : fieldErrors.id}
      >
        <input
          className={`${FIELD_INPUT} ${mode === "edit" ? "opacity-60" : ""}`}
          value={form.id}
          disabled={mode === "edit"}
          aria-label={t("adminContent.editor.idLabel")}
          placeholder={config.idPlaceholder}
          autoComplete="off"
          spellCheck={false}
          onChange={(event) => {
            const next = event.target.value.trim().toLowerCase();
            setForm((prev) => ({ ...prev, id: next }));
            setFieldErrors((prev) => ({ ...prev, id: "" }));
          }}
        />
      </Labeled>

      {config.hasCategory && (
        <Labeled label={t("adminContent.editor.categoryLabel")} required error={fieldErrors.category_id}>
          <select
            className={FIELD_INPUT}
            value={form.category_id}
            aria-label={t("adminContent.editor.categoryLabel")}
            onChange={(event) => {
              const next = event.target.value;
              setForm((prev) => ({ ...prev, category_id: next }));
              setFieldErrors((prev) => ({ ...prev, category_id: "" }));
            }}
          >
            <option value="" disabled>
              {t("adminContent.editor.categoryPlaceholder")}
            </option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name.uz}
              </option>
            ))}
          </select>
        </Labeled>
      )}

      <Labeled label={t("adminContent.editor.sortOrderLabel")}>
        <input
          type="number"
          className={FIELD_INPUT}
          value={form.sort_order}
          aria-label={t("adminContent.editor.sortOrderLabel")}
          onChange={(event) =>
            setForm((prev) => ({ ...prev, sort_order: Number(event.target.value) || 0 }))
          }
        />
      </Labeled>

      {config.hasPublished && (
        <ToggleRow
          label={t("adminContent.editor.publishedLabel")}
          checked={form.published}
          onChange={(value) => setForm((prev) => ({ ...prev, published: value }))}
        />
      )}
    </div>
  );

  const langRow = (
    <div className="mb-2 flex items-center justify-between gap-2">
      <span className="text-[11px] font-semibold text-muted">{t("adminContent.editor.langTabs")}</span>
      <SegmentedControl
        options={LANGS.map((lang) => ({
          value: lang,
          label: `${LANG_META[lang].native}${invalidLang(lang) ? " !" : ""}`,
        }))}
        value={activeLang}
        onChange={(lang) => setActiveLang(lang)}
        ariaLabel={t("adminContent.editor.langTabs")}
      />
    </div>
  );

  const titles = (
    <div className="space-y-2">
      {langRow}
      <RichTextField
        label={t(config.titleLabelKey)}
        required
        value={localizedValue(form.title, activeLang)}
        onChange={(value) => setField("title", activeLang, value)}
        maxLen={config.titleMaxLen}
        rows={2}
        toolbar={config.hasBody}
        errorText={fieldErrors[`${config.titleField}.${activeLang}`]}
      />
      {config.hasBody && (
        <RichTextField
          label={t("adminContent.editor.fieldSummary")}
          required
          value={localizedValue(form.summary, activeLang)}
          onChange={(value) => setField("summary", activeLang, value)}
          maxLen={FIELD_MAX_LEN.summary}
          rows={3}
          errorText={fieldErrors[`summary.${activeLang}`]}
        />
      )}
    </div>
  );

  const items: AccordionItem[] = [
    { id: "basic", titleKey: "adminContent.section.basic", content: basic },
    { id: "titles", titleKey: config.titleSectionKey, content: titles },
  ];

  if (config.hasBody) {
    items.push({
      id: "body",
      titleKey: "adminContent.section.body",
      content: (
        <div className="space-y-2">
          {langRow}
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
      ),
    });
  }

  if (config.hasSource) {
    items.push({
      id: "source",
      titleKey: "adminContent.section.source",
      content: (
        <div className="space-y-2">
          <Labeled label={t("adminContent.editor.sourceUrlLabel")} hint={t("adminContent.editor.optionalHint")}>
            <input
              type="url"
              className={FIELD_INPUT}
              value={form.source_url}
              aria-label={t("adminContent.editor.sourceUrlLabel")}
              placeholder="https://lex.uz/..."
              onChange={(event) => setForm((prev) => ({ ...prev, source_url: event.target.value }))}
            />
          </Labeled>
          {langRow}
          <RichTextField
            label={t("adminContent.editor.fieldSourceLabel")}
            value={localizedValue(form.source_label, activeLang)}
            onChange={(value) => setField("source_label", activeLang, value)}
            maxLen={FIELD_MAX_LEN.source_label}
            rows={1}
            toolbar={false}
            errorText={fieldErrors[`source_label.${activeLang}`]}
          />
        </div>
      ),
    });
  }

  return (
    <div className="space-y-2 pb-2">
      {dirty && (
        <p className="text-[11px] font-semibold text-warning">{t("adminContent.editor.unsavedBadge")}</p>
      )}
      <Accordion items={items} defaultOpen="basic" />
    </div>
  );
}

/**
 * `/admin/content/:kind/:id` (and `/new`). The admin lists are small and flat,
 * so the record is read out of the kind's list query — one cache for the list
 * screen and the editor, and no extra request on the way in.
 */
export default function ContentEditor({ kind, id }: { kind: ContentKind; id: string | null }) {
  const config = CONTENT_CONFIG[kind];
  const query = useQuery({
    queryKey: config.queryKey(),
    queryFn: config.list,
    retry: false,
    enabled: id !== null,
  });

  if (id === null) return <EditorForm kind={kind} initial={null} />;
  if (query.isLoading) return <Skeleton rows={6} />;
  if (query.isError) return <ErrorCard error={query.error} onRetry={() => void query.refetch()} />;

  const record = query.data?.items.find((item) => item.id === id) ?? null;
  if (!record) {
    return (
      <EmptyState
        labelKey="adminContent.error.notFound"
        action={<Button labelKey="adminContent.editor.backToList" to={contentPath(kind)} />}
      />
    );
  }

  return <EditorForm key={record.id} kind={kind} initial={record} />;
}
