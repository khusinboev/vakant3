import type { TFunction } from "../../../i18n";
import type { ResumeDoc, StepId } from "../types";

export const MIN_SKILLS = 3;
export const MIN_SUMMARY_CHARS = 40;

/** A step is "done" once it holds enough content to be worth a green tick. */
export function isStepDone(id: StepId, doc: ResumeDoc): boolean {
  const { profile } = doc;
  switch (id) {
    case "basic":
      return Boolean(profile.full_name.trim() && profile.position.trim());
    case "experience":
      return profile.experiences.some((item) => item.role || item.company || item.description);
    case "education":
      return profile.educations.some((item) => item.school || item.degree || item.description);
    case "skills":
      return profile.skills.length >= MIN_SKILLS;
    case "summary":
      return profile.summary.trim().length >= MIN_SUMMARY_CHARS;
    case "template":
      return Boolean(doc.selectedTemplate);
    default:
      return false;
  }
}

/** Field name -> translated message. Empty means the step may be left. */
export function validateStep(id: StepId, doc: ResumeDoc, t: TFunction): Record<string, string> {
  const { profile } = doc;
  const errors: Record<string, string> = {};

  if (id === "basic") {
    if (!profile.full_name.trim()) errors.full_name = t("resume.err.fullName");
    if (!profile.position.trim()) errors.position = t("resume.err.position");
    if (!profile.email.trim() && !profile.phone.trim()) errors.contact = t("resume.err.contact");
  }

  if (id === "experience") {
    if (profile.experiences.length === 0) {
      errors.experience = t("resume.err.experienceRequired");
    } else if (profile.experiences.some((item) => !item.role.trim() || !item.company.trim())) {
      errors.experience = t("resume.err.experienceFields");
    }
  }

  if (id === "education" && profile.educations.length === 0) {
    errors.education = t("resume.err.educationRequired");
  }

  if (id === "skills" && profile.skills.length < MIN_SKILLS) {
    errors.skills = t("resume.err.skillsMin", { n: MIN_SKILLS });
  }

  if (id === "summary" && profile.summary.trim().length < MIN_SUMMARY_CHARS) {
    errors.summary = t("resume.err.summaryMin", { n: MIN_SUMMARY_CHARS });
  }

  if (id === "template" && !doc.selectedTemplate) {
    errors.template = t("resume.err.templateRequired");
  }

  return errors;
}
