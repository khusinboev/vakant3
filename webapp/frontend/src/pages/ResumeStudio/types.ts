/** Wire + form types for the resume wizard (mirrors `webapp/resume/schemas.py`). */

export type ResumeExperienceItem = {
  role: string;
  company: string;
  start_date: string;
  end_date: string;
  location: string;
  description: string;
};

export type ResumeEducationItem = {
  school: string;
  degree: string;
  start_date: string;
  end_date: string;
  description: string;
};

export type ResumeProfileData = {
  full_name: string;
  position: string;
  phone: string;
  email: string;
  location: string;
  website: string;
  summary: string;
  experiences: ResumeExperienceItem[];
  educations: ResumeEducationItem[];
  skills: string[];
  languages: string[];
  photo_url: string;
};

export type ResumeProfileResponse = {
  profile: ResumeProfileData;
  selected_template: string;
  accent_color: string;
  /** Unix seconds, or null when nothing was ever saved. */
  updated_at: number | null;
};

export type ResumeTemplateItem = {
  id: string;
  /** Localized by the API (`Accept-Language`); empty for the local fallback list. */
  title: string;
  description: string;
  supports_color: boolean;
  supports_photo?: boolean;
  supports_sidebar?: boolean;
  preview_variant: "single" | "split" | "mono";
  palette: string[];
  is_premium?: boolean;
};

/** POST /api/resume/events — names and steps are allowlisted server-side. */
export type ResumeEventPayload = {
  event_name: string;
  step?: string;
  meta_json?: string;
};

export type StepId = "basic" | "experience" | "education" | "skills" | "summary" | "template";

/** The wizard state that is persisted, both locally and to the API. */
export type ResumeDoc = {
  profile: ResumeProfileData;
  selectedTemplate: string;
  accentColor: string;
};

export type LocalDraft = ResumeDoc & {
  jobDescription: string;
  /** Epoch milliseconds. */
  updatedAt: number;
};

export const DEFAULT_TEMPLATE = "clean";
export const DEFAULT_ACCENT = "#0f766e";

export const EMPTY_PROFILE: ResumeProfileData = {
  full_name: "",
  position: "",
  phone: "",
  email: "",
  location: "",
  website: "",
  summary: "",
  experiences: [],
  educations: [],
  skills: [],
  languages: [],
  photo_url: "",
};

export const EMPTY_EXPERIENCE: ResumeExperienceItem = {
  role: "",
  company: "",
  start_date: "",
  end_date: "",
  location: "",
  description: "",
};

export const EMPTY_EDUCATION: ResumeEducationItem = {
  school: "",
  degree: "",
  start_date: "",
  end_date: "",
  description: "",
};

function str(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

/** Coerce anything the API or localStorage hands back into a complete profile. */
export function normalizeProfile(input: Partial<ResumeProfileData> | null | undefined): ResumeProfileData {
  return {
    full_name: str(input?.full_name),
    position: str(input?.position),
    phone: str(input?.phone),
    email: str(input?.email),
    location: str(input?.location),
    website: str(input?.website),
    summary: str(input?.summary),
    experiences: Array.isArray(input?.experiences)
      ? input.experiences.map((item) => ({
          role: str(item?.role),
          company: str(item?.company),
          start_date: str(item?.start_date),
          end_date: str(item?.end_date),
          location: str(item?.location),
          description: str(item?.description),
        }))
      : [],
    educations: Array.isArray(input?.educations)
      ? input.educations.map((item) => ({
          school: str(item?.school),
          degree: str(item?.degree),
          start_date: str(item?.start_date),
          end_date: str(item?.end_date),
          description: str(item?.description),
        }))
      : [],
    skills: Array.isArray(input?.skills) ? input.skills.map(str).filter(Boolean) : [],
    languages: Array.isArray(input?.languages) ? input.languages.map(str).filter(Boolean) : [],
    photo_url: str(input?.photo_url),
  };
}

/** True when the user has entered anything at all. */
export function profileHasContent(profile: ResumeProfileData): boolean {
  return Boolean(
    profile.full_name ||
      profile.position ||
      profile.phone ||
      profile.email ||
      profile.location ||
      profile.website ||
      profile.summary ||
      profile.experiences.length ||
      profile.educations.length ||
      profile.skills.length ||
      profile.languages.length ||
      profile.photo_url,
  );
}

/**
 * Change signature used to decide whether a save is still current.
 * The photo is reduced to its length: a 100 KB data URI is far too expensive to
 * stringify on every keystroke, and its length changes whenever it does.
 */
export function makeFingerprint(doc: ResumeDoc): string {
  const { photo_url, ...rest } = doc.profile;
  return JSON.stringify({
    profile: rest,
    photo: photo_url ? photo_url.length : 0,
    template: doc.selectedTemplate,
    accent: doc.accentColor,
  });
}
