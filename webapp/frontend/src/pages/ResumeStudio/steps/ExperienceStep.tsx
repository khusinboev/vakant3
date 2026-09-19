import { AlertCircle, Briefcase, Plus, Trash2 } from "lucide-react";

import Field, { INPUT_CLS } from "../../../components/ui/Field";
import MonthYearPicker from "../../../components/ui/MonthYearPicker";
import { formatMonthYear } from "../../../components/ui/monthYear";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import { roleSuggestionKeys } from "../lib/keywords";
import type { StepProps } from "./common";

export default function ExperienceStep({ draft, errors }: StepProps) {
  const t = useT();
  const { locale } = useLocale();
  const { profile, expKeys, addExperience, removeExperience, updateExperience, appendExperienceBullet } = draft;
  const optional = `(${t("common.optional")})`;
  const presentLabel = t("resume.date.presentShort");

  return (
    <div className="space-y-3">
      {profile.experiences.length === 0 && (
        <div className="rounded-2xl border-2 border-dashed border-border bg-surface p-8 text-center">
          <Briefcase size={36} className="mx-auto mb-3 text-muted/50" />
          <p className="text-sm font-semibold text-muted">{t("resume.exp.empty")}</p>
          <p className="mt-1 text-xs text-muted/80">{t("resume.exp.emptyHint")}</p>
        </div>
      )}

      {profile.experiences.map((exp, index) => {
        const period = [exp.start_date, exp.end_date]
          .map((value) => formatMonthYear(value, locale, presentLabel))
          .filter(Boolean)
          .join(" – ");

        return (
          <div
            key={expKeys[index] ?? String(index)}
            className="overflow-hidden rounded-2xl border border-border bg-surface"
          >
            <div className="flex items-center gap-3 border-b border-border bg-surfaceAlt px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-text">
                  {exp.role || exp.company
                    ? `${exp.role || t("resume.exp.roleFallback")} @ ${exp.company || t("resume.exp.companyFallback")}`
                    : t("resume.exp.item", { n: index + 1 })}
                </p>
                {period && <p className="mt-0.5 text-xs text-muted">{period}</p>}
              </div>
              <button
                type="button"
                aria-label={t("resume.exp.remove")}
                className="shrink-0 rounded-xl border border-danger/30 p-2 text-danger transition-colors hover:bg-danger/10"
                onClick={() => removeExperience(index)}
              >
                <Trash2 size={14} />
              </button>
            </div>

            <div className="space-y-3 p-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label={t("resume.exp.role")}>
                  <input
                    className={INPUT_CLS}
                    placeholder={t("resume.ph.role")}
                    value={exp.role}
                    onChange={(event) => updateExperience(index, "role", event.target.value)}
                  />
                </Field>
                <Field label={t("resume.exp.company")}>
                  <input
                    className={INPUT_CLS}
                    placeholder={t("resume.ph.company")}
                    value={exp.company}
                    onChange={(event) => updateExperience(index, "company", event.target.value)}
                  />
                </Field>
                <Field label={t("resume.exp.start")}>
                  <MonthYearPicker
                    value={exp.start_date}
                    onChange={(value) => updateExperience(index, "start_date", value)}
                  />
                </Field>
                <Field label={t("resume.exp.end")}>
                  <MonthYearPicker
                    value={exp.end_date}
                    onChange={(value) => updateExperience(index, "end_date", value)}
                    withCurrent
                  />
                </Field>
              </div>

              <Field label={t("resume.exp.location")} hint={optional}>
                <input
                  className={INPUT_CLS}
                  placeholder={t("resume.ph.expLocation")}
                  value={exp.location}
                  onChange={(event) => updateExperience(index, "location", event.target.value)}
                />
              </Field>

              <Field label={t("resume.exp.description")}>
                <textarea
                  className={`${INPUT_CLS} min-h-[96px] resize-none`}
                  placeholder={t("resume.ph.expDescription")}
                  value={exp.description}
                  onChange={(event) => updateExperience(index, "description", event.target.value)}
                />
              </Field>

              <div className="flex flex-wrap gap-1.5">
                {roleSuggestionKeys(exp.role)
                  .slice(0, 2)
                  .map((key) => {
                    const text = t(key);
                    return (
                      <button
                        type="button"
                        key={key}
                        className="rounded-full border border-success/30 bg-success/10 px-2.5 py-1 text-left text-[11px] text-success"
                        onClick={() => appendExperienceBullet(index, text)}
                      >
                        + {text.slice(0, 38)}…
                      </button>
                    );
                  })}
              </div>
            </div>
          </div>
        );
      })}

      {errors.experience && (
        <p className="flex items-center gap-1.5 px-1 text-xs text-danger">
          <AlertCircle size={12} className="shrink-0" /> {errors.experience}
        </p>
      )}

      <button
        type="button"
        className="tap-target flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-primary/40 bg-primary/5 py-3.5 text-sm font-semibold text-primary transition-colors hover:bg-primary/10"
        onClick={addExperience}
      >
        <Plus size={16} /> {t("resume.exp.add")}
      </button>
    </div>
  );
}
