import { AlertCircle, GraduationCap, Plus, Trash2 } from "lucide-react";

import Field, { INPUT_CLS } from "../../../components/ui/Field";
import MonthYearPicker from "../../../components/ui/MonthYearPicker";
import StyledSelect from "../../../components/ui/StyledSelect";
import { formatMonthYear } from "../../../components/ui/monthYear";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { DEGREE_KEYS } from "../data/templates";
import type { StepProps } from "./common";

export default function EducationStep({ draft, errors }: StepProps) {
  const t = useT();
  const { locale } = useLocale();
  const { profile, eduKeys, addEducation, removeEducation, updateEducation } = draft;
  const optional = `(${t("common.optional")})`;
  const presentLabel = t("resume.date.presentShort");
  const degrees = DEGREE_KEYS.map((key) => t(key));

  return (
    <div className="space-y-3">
      {profile.educations.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-border bg-surface p-8 text-center">
          <GraduationCap size={36} className="mx-auto mb-3 text-muted/50" />
          <p className="text-sm font-semibold text-muted">{t("resume.edu.empty")}</p>
          <p className="mt-1 text-xs text-muted/80">{t("resume.edu.emptyHint")}</p>
        </div>
      )}

      {profile.educations.map((edu, index) => {
        const period = [edu.start_date, edu.end_date]
          .map((value) => formatMonthYear(value, locale, presentLabel))
          .filter(Boolean)
          .join(" – ");
        // A degree saved in another language stays selectable.
        const unknownDegree = Boolean(edu.degree) && !degrees.includes(edu.degree);

        return (
          <div
            key={eduKeys[index] ?? String(index)}
            className="overflow-hidden rounded-2xl border border-border bg-surface"
          >
            <div className="flex items-center gap-3 border-b border-border bg-surfaceAlt px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-text">
                  {edu.school || edu.degree
                    ? `${edu.school || t("resume.edu.schoolFallback")} — ${edu.degree || t("resume.edu.degreeFallback")}`
                    : t("resume.edu.item", { n: index + 1 })}
                </p>
                {period && <p className="mt-0.5 text-xs text-muted">{period}</p>}
              </div>
              <button
                type="button"
                aria-label={t("resume.edu.remove")}
                className="shrink-0 rounded-xl border border-danger/30 p-2 text-danger transition-colors hover:bg-danger/10"
                onClick={() => removeEducation(index)}
              >
                <Trash2 size={14} />
              </button>
            </div>

            <div className="space-y-3 p-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label={t("resume.edu.school")}>
                  <input
                    className={INPUT_CLS}
                    placeholder={t("resume.ph.school")}
                    value={edu.school}
                    onChange={(event) => updateEducation(index, "school", event.target.value)}
                  />
                </Field>
                <Field label={t("resume.edu.degree")}>
                  <StyledSelect
                    aria-label={t("resume.edu.degree")}
                    value={edu.degree}
                    onChange={(event) => updateEducation(index, "degree", event.target.value)}
                  >
                    <option value="">{t("resume.edu.selectDegree")}</option>
                    {unknownDegree && <option value={edu.degree}>{edu.degree}</option>}
                    {degrees.map((degree) => (
                      <option key={degree} value={degree}>
                        {degree}
                      </option>
                    ))}
                  </StyledSelect>
                </Field>
                <Field label={t("resume.edu.start")}>
                  <MonthYearPicker
                    value={edu.start_date}
                    onChange={(value) => updateEducation(index, "start_date", value)}
                  />
                </Field>
                <Field label={t("resume.edu.end")}>
                  <MonthYearPicker
                    value={edu.end_date}
                    onChange={(value) => updateEducation(index, "end_date", value)}
                    withCurrent
                  />
                </Field>
              </div>

              <Field label={t("resume.edu.description")} hint={optional}>
                <textarea
                  className={`${INPUT_CLS} min-h-[72px] resize-none`}
                  placeholder={t("resume.ph.eduDescription")}
                  value={edu.description}
                  onChange={(event) => updateEducation(index, "description", event.target.value)}
                />
              </Field>
            </div>
          </div>
        );
      })}

      {errors.education && (
        <p className="flex items-center gap-1.5 px-1 text-xs text-danger">
          <AlertCircle size={12} className="shrink-0" /> {errors.education}
        </p>
      )}

      <button
        type="button"
        className="tap-target flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-primary/40 bg-primary/5 py-3.5 text-sm font-semibold text-primary transition-colors hover:bg-primary/10"
        onClick={addEducation}
      >
        <Plus size={16} /> {t("resume.edu.add")}
      </button>
    </div>
  );
}
