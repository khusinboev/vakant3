import Field from "../../../components/ui/Field";
import TagInput from "../../../components/ui/TagInput";
import { useT } from "../../../i18n/useT";
import { SKILL_SUGGESTIONS } from "../lib/keywords";
import { MIN_SKILLS } from "../lib/validation";
import type { StepProps } from "./common";

export default function SkillsStep({ draft, errors }: StepProps) {
  const t = useT();
  const { profile, setProfile } = draft;

  const addSkill = (skill: string) => setProfile((p) => ({ ...p, skills: [...p.skills, skill] }));
  const suggestions = SKILL_SUGGESTIONS.filter(
    (skill) => !profile.skills.some((item) => item.toLowerCase() === skill.toLowerCase()),
  ).slice(0, 8);

  return (
    <div className="space-y-4">
      <Field label={t("resume.skills.label")} hint={t("resume.skills.hint")} error={errors.skills}>
        <TagInput
          tags={profile.skills}
          onAdd={addSkill}
          onRemove={(index) =>
            setProfile((p) => ({ ...p, skills: p.skills.filter((_, i) => i !== index) }))
          }
          placeholder={t("resume.ph.skills")}
        />
        <p className="text-xs text-muted">
          {t("resume.skills.count", { n: profile.skills.length })}
          {profile.skills.length < MIN_SKILLS && (
            <span className="ml-1 text-warning">{t("resume.skills.min", { n: MIN_SKILLS })}</span>
          )}
        </p>
      </Field>

      <Field label={t("resume.languages.label")} hint={t("resume.skills.hint")}>
        <TagInput
          tags={profile.languages}
          onAdd={(language) => setProfile((p) => ({ ...p, languages: [...p.languages, language] }))}
          onRemove={(index) =>
            setProfile((p) => ({ ...p, languages: p.languages.filter((_, i) => i !== index) }))
          }
          placeholder={t("resume.ph.languages")}
        />
      </Field>

      {profile.position && suggestions.length > 0 && (
        <div className="rounded-2xl border border-border bg-surface p-4">
          <p className="mb-2.5 text-xs font-semibold text-muted">
            {t("resume.skills.suggestTitle", { position: profile.position })}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {suggestions.map((skill) => (
              <button
                type="button"
                key={skill}
                className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
                onClick={() => addSkill(skill)}
              >
                + {skill}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
