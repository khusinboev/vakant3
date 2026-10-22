import { useMemo } from "react";
import { Check } from "lucide-react";

import Field, { INPUT_CLS } from "../../../components/ui/Field";
import { useT } from "../../../i18n/useT";
import { extractTopKeywords } from "../lib/keywords";
import { MIN_SUMMARY_CHARS } from "../lib/validation";
import type { StepProps } from "./common";

export default function SummaryStep({ draft, errors }: StepProps) {
  const t = useT();
  const { profile, patchProfile, jobDescription, setJobDescription, setProfile } = draft;

  // Everything already written, lower-cased, to test keywords against.
  const resumeCorpus = useMemo(() => {
    const experience = profile.experiences
      .map((item) => [item.role, item.company, item.description].join(" "))
      .join(" ");
    const education = profile.educations
      .map((item) => [item.school, item.degree, item.description].join(" "))
      .join(" ");
    return [profile.full_name, profile.position, profile.summary, experience, education, profile.skills.join(" ")]
      .join(" ")
      .toLowerCase();
  }, [profile]);

  const topKeywords = useMemo(() => extractTopKeywords(jobDescription), [jobDescription]);
  const missingKeywords = useMemo(
    () => topKeywords.filter((keyword) => !resumeCorpus.includes(keyword)).slice(0, 8),
    [topKeywords, resumeCorpus],
  );

  return (
    <div className="space-y-4">
      <Field label={t("resume.summary.label")} error={errors.summary}>
        <textarea
          className={`${INPUT_CLS} min-h-[130px] resize-none`}
          placeholder={t("resume.ph.summary")}
          value={profile.summary}
          onChange={(event) => patchProfile({ summary: event.target.value })}
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted">{t("resume.summary.minHint", { n: MIN_SUMMARY_CHARS })}</span>
          <span
            className={`text-xs font-semibold ${
              profile.summary.length >= MIN_SUMMARY_CHARS ? "text-success" : "text-muted"
            }`}
          >
            {t("resume.summary.charCount", { n: profile.summary.length })}
          </span>
        </div>
      </Field>

      <div className="overflow-hidden rounded-2xl border border-warning/30 bg-warning/10">
        <div className="border-b border-warning/30 px-4 py-3">
          <p className="text-xs font-bold text-warning">{t("resume.match.title")}</p>
          <p className="mt-0.5 text-[11px] text-muted">{t("resume.match.subtitle")}</p>
        </div>

        <div className="space-y-3 p-4">
          <textarea
            className={`${INPUT_CLS} min-h-[90px] resize-none`}
            placeholder={t("resume.ph.jobDescription")}
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
          />

          {topKeywords.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-muted">
                {t("resume.match.topKeywords")}{" "}
                <span className="font-medium text-text">{topKeywords.slice(0, 6).join(", ")}</span>
              </p>

              {missingKeywords.length > 0 ? (
                <div>
                  <p className="mb-1.5 text-xs font-semibold text-warning">{t("resume.match.missing")}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {missingKeywords.map((keyword) => (
                      <button
                        type="button"
                        key={keyword}
                        className="rounded-full border border-warning/40 bg-surface px-2.5 py-1 text-[11px] font-medium text-warning"
                        onClick={() => setProfile((p) => ({ ...p, skills: [...p.skills, keyword] }))}
                      >
                        + {keyword}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="flex items-center gap-1 text-xs font-semibold text-success">
                  <Check size={12} /> {t("resume.match.allPresent")}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
