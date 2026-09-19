import { Briefcase, FileEdit, GraduationCap, Palette, User, Zap } from "lucide-react";

import type { TFunction, TranslationKey } from "../../../i18n";
import type { ResumeTemplateItem, StepId } from "../types";

// ── Wizard steps ────────────────────────────────────────────────────────────

export type StepDef = {
  id: StepId;
  labelKey: TranslationKey;
  hintKey: TranslationKey;
  icon: typeof User;
};

export const STEPS: StepDef[] = [
  { id: "basic", labelKey: "resume.step.basic", hintKey: "resume.hint.basic", icon: User },
  { id: "experience", labelKey: "resume.step.experience", hintKey: "resume.hint.experience", icon: Briefcase },
  { id: "education", labelKey: "resume.step.education", hintKey: "resume.hint.education", icon: GraduationCap },
  { id: "skills", labelKey: "resume.step.skills", hintKey: "resume.hint.skills", icon: Zap },
  { id: "summary", labelKey: "resume.step.summary", hintKey: "resume.hint.summary", icon: FileEdit },
  { id: "template", labelKey: "resume.step.template", hintKey: "resume.hint.template", icon: Palette },
];

// ── Degrees ─────────────────────────────────────────────────────────────────

/**
 * The selected label is stored verbatim and printed into the PDF, so the option
 * list is localized and an unknown stored value is kept as an extra option.
 */
export const DEGREE_KEYS: TranslationKey[] = [
  "resume.degree.secondary",
  "resume.degree.vocational",
  "resume.degree.bachelor",
  "resume.degree.master",
  "resume.degree.phd",
  "resume.degree.courses",
  "resume.degree.other",
];

// ── Templates ───────────────────────────────────────────────────────────────

/** Mirrors `FREE_TEMPLATES` in `webapp/resume/schemas.py`. */
export const FREE_TEMPLATE_IDS: ReadonlySet<string> = new Set(["clean", "modern", "compact"]);

/** Templates whose PDF header is dark, so the preview can flag it. */
export const DARK_TEMPLATE_IDS: ReadonlySet<string> = new Set(["executive", "infographic"]);

type TemplateMeta = Omit<ResumeTemplateItem, "title" | "description" | "is_premium">;

/**
 * Offline fallback for `GET /api/resume/templates`. Titles and descriptions come
 * from the `resume.tplTitle.*` / `resume.tplDesc.*` keys; the API sends its own,
 * already localized by `Accept-Language`.
 */
const LOCAL_TEMPLATE_META: TemplateMeta[] = [
  {
    id: "clean",
    supports_color: true,
    preview_variant: "single",
    palette: ["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
  },
  {
    id: "modern",
    supports_color: true,
    supports_sidebar: true,
    preview_variant: "split",
    palette: ["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
  },
  {
    id: "compact",
    supports_color: false,
    preview_variant: "mono",
    palette: ["#111827"],
  },
  {
    id: "executive",
    supports_color: true,
    preview_variant: "single",
    palette: ["#1e3a5f", "#7c2d12", "#164e63", "#3b0764", "#1c1917"],
  },
  {
    id: "timeline",
    supports_color: true,
    preview_variant: "single",
    palette: ["#0f766e", "#2563eb", "#7c3aed", "#b45309", "#065f46"],
  },
  {
    id: "minimal",
    supports_color: false,
    preview_variant: "mono",
    palette: ["#111827"],
  },
  {
    id: "creative",
    supports_color: true,
    preview_variant: "single",
    palette: ["#7c3aed", "#ea580c", "#be123c", "#0f766e", "#1d4ed8"],
  },
  {
    id: "photo_classic",
    supports_color: true,
    supports_photo: true,
    preview_variant: "single",
    palette: ["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
  },
  {
    id: "photo_sidebar",
    supports_color: true,
    supports_photo: true,
    supports_sidebar: true,
    preview_variant: "split",
    palette: ["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
  },
  {
    id: "europass",
    supports_color: true,
    supports_photo: true,
    preview_variant: "split",
    palette: ["#1e40af", "#065f46", "#7c2d12", "#4c1d95", "#374151"],
  },
  {
    id: "infographic",
    supports_color: true,
    preview_variant: "single",
    palette: ["#0f766e", "#2563eb", "#ea580c", "#7c3aed", "#1e3a5f"],
  },
];

/** Translated title/description for a template id, used as a fallback. */
export function templateStrings(t: TFunction, id: string): { title: string; description: string } {
  const titleKey = `resume.tplTitle.${id}` as TranslationKey;
  const descKey = `resume.tplDesc.${id}` as TranslationKey;
  const title = t(titleKey);
  const description = t(descKey);
  return {
    title: title === titleKey ? id : title,
    description: description === descKey ? "" : description,
  };
}

/**
 * The template list the wizard renders: the API catalogue when it loaded, the
 * local fallback otherwise. `is_premium` is filled in locally as well, so a
 * premium template is greyed out even when the API omits the flag.
 */
export function resolveTemplates(t: TFunction, apiItems?: ResumeTemplateItem[]): ResumeTemplateItem[] {
  const source: Array<TemplateMeta & Partial<ResumeTemplateItem>> = apiItems?.length
    ? apiItems
    : LOCAL_TEMPLATE_META;

  return source.map((item) => {
    const strings = templateStrings(t, item.id);
    return {
      ...item,
      title: item.title || strings.title,
      description: item.description || strings.description,
      is_premium: item.is_premium ?? !FREE_TEMPLATE_IDS.has(item.id),
    };
  });
}

export function premiumTemplateCount(templates: ResumeTemplateItem[]): number {
  return templates.filter((item) => item.is_premium).length;
}
