import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DEFAULT_ACCENT,
  DEFAULT_TEMPLATE,
  EMPTY_EDUCATION,
  EMPTY_EXPERIENCE,
  EMPTY_PROFILE,
  makeFingerprint,
  normalizeProfile,
  profileHasContent,
  type LocalDraft,
  type ResumeDoc,
  type ResumeEducationItem,
  type ResumeExperienceItem,
  type ResumeProfileData,
  type ResumeProfileResponse,
} from "./types";

const DRAFT_KEY = "resume_wizard_draft_v2";
const PHOTO_KEY = "resume_wizard_photo_v1";
const SAVE_DEBOUNCE_MS = 900;

// localStorage is shared by every Telegram account that opens the Mini App on
// this device, so both keys are scoped by user id — an unscoped key would leak
// one person's resume draft into another account.
const draftKey = (userId: number) => `${DRAFT_KEY}:${userId}`;
const photoKey = (userId: number) => `${PHOTO_KEY}:${userId}`;

type StoredDraft = Partial<{
  profile: Partial<ResumeProfileData>;
  selectedTemplate: string;
  accentColor: string;
  jobDescription: string;
  updatedAt: number;
  // v1 field names, still found in browsers that used the old page.
  selected_template: string;
  accent_color: string;
  job_description: string;
  updated_at: number;
}>;

function readLocalDraft(userId: number): LocalDraft | null {
  try {
    const raw = localStorage.getItem(draftKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredDraft;
    const photo = localStorage.getItem(photoKey(userId)) || "";
    return {
      profile: { ...normalizeProfile(parsed.profile), photo_url: photo },
      selectedTemplate: String(parsed.selectedTemplate || parsed.selected_template || DEFAULT_TEMPLATE),
      accentColor: String(parsed.accentColor || parsed.accent_color || DEFAULT_ACCENT),
      jobDescription: String(parsed.jobDescription || parsed.job_description || ""),
      updatedAt: Number(parsed.updatedAt || parsed.updated_at || 0),
    };
  } catch {
    return null;
  }
}

function writeLocalDraft(userId: number, draft: LocalDraft, lastPhoto: string): string {
  // The base64 photo never goes into the draft JSON: it can be hundreds of KB
  // and would be re-serialized on every keystroke. It lives in its own key and
  // is only rewritten when it actually changed.
  const { photo_url: photo, ...profile } = draft.profile;
  try {
    localStorage.setItem(
      draftKey(userId),
      JSON.stringify({
        profile: { ...profile, photo_url: "" },
        selectedTemplate: draft.selectedTemplate,
        accentColor: draft.accentColor,
        jobDescription: draft.jobDescription,
        updatedAt: draft.updatedAt,
      }),
    );
    if (photo !== lastPhoto) {
      if (photo) localStorage.setItem(photoKey(userId), photo);
      else localStorage.removeItem(photoKey(userId));
    }
  } catch {
    // Quota exceeded / private mode: the server copy is the real store.
  }
  return photo;
}

export type ResumeDraft = ReturnType<typeof useResumeDraft>;

/**
 * Wizard form state plus its localStorage draft.
 *
 * On mount (once the Telegram user id is known) an unsaved draft is restored and
 * flagged dirty so the next autosave pushes it to the API; `localDraftAtRef`
 * carries its timestamp so the caller can compare it with the server's.
 */
export function useResumeDraft(userId: number | undefined, onRestored: () => void) {
  const [profile, setProfileState] = useState<ResumeProfileData>(EMPTY_PROFILE);
  const [selectedTemplate, setSelectedTemplateState] = useState(DEFAULT_TEMPLATE);
  const [accentColor, setAccentColorState] = useState(DEFAULT_ACCENT);
  const [jobDescription, setJobDescriptionState] = useState("");
  const [dirty, setDirty] = useState(false);
  // Stable React keys for the repeatable lists (avoids flicker when deleting).
  const [expKeys, setExpKeys] = useState<string[]>([]);
  const [eduKeys, setEduKeys] = useState<string[]>([]);

  const dirtyRef = useRef(false);
  const restoredRef = useRef(false);
  const localDraftAtRef = useRef(0);
  const lastPhotoRef = useRef("");
  const onRestoredRef = useRef(onRestored);
  onRestoredRef.current = onRestored;

  const markDirty = useCallback(() => {
    dirtyRef.current = true;
    setDirty(true);
  }, []);

  const genKey = () => `k_${Date.now()}_${Math.random().toString(36).slice(2)}`;

  const setProfile = useCallback(
    (updater: (previous: ResumeProfileData) => ResumeProfileData) => {
      setProfileState(updater);
      markDirty();
    },
    [markDirty],
  );

  const patchProfile = useCallback(
    (patch: Partial<ResumeProfileData>) => setProfile((previous) => ({ ...previous, ...patch })),
    [setProfile],
  );

  const setSelectedTemplate = useCallback(
    (id: string) => {
      setSelectedTemplateState(id);
      markDirty();
    },
    [markDirty],
  );

  const setAccentColor = useCallback(
    (color: string, silent = false) => {
      setAccentColorState(color);
      if (!silent) markDirty();
    },
    [markDirty],
  );

  const setJobDescription = useCallback((value: string) => setJobDescriptionState(value), []);

  // ── Repeatable lists ──────────────────────────────────────────────────────
  const addExperience = useCallback(() => {
    setProfile((p) => ({ ...p, experiences: [...p.experiences, { ...EMPTY_EXPERIENCE }] }));
    setExpKeys((keys) => [...keys, genKey()]);
  }, [setProfile]);

  const removeExperience = useCallback(
    (index: number) => {
      setProfile((p) => ({ ...p, experiences: p.experiences.filter((_, i) => i !== index) }));
      setExpKeys((keys) => keys.filter((_, i) => i !== index));
    },
    [setProfile],
  );

  const updateExperience = useCallback(
    (index: number, key: keyof ResumeExperienceItem, value: string) => {
      setProfile((p) => {
        const experiences = [...p.experiences];
        experiences[index] = { ...experiences[index], [key]: value };
        return { ...p, experiences };
      });
    },
    [setProfile],
  );

  const appendExperienceBullet = useCallback(
    (index: number, text: string) => {
      setProfile((p) => {
        const experiences = [...p.experiences];
        const previous = experiences[index]?.description?.trim() || "";
        experiences[index] = {
          ...experiences[index],
          description: previous ? `${previous}\n- ${text}` : `- ${text}`,
        };
        return { ...p, experiences };
      });
    },
    [setProfile],
  );

  const addEducation = useCallback(() => {
    setProfile((p) => ({ ...p, educations: [...p.educations, { ...EMPTY_EDUCATION }] }));
    setEduKeys((keys) => [...keys, genKey()]);
  }, [setProfile]);

  const removeEducation = useCallback(
    (index: number) => {
      setProfile((p) => ({ ...p, educations: p.educations.filter((_, i) => i !== index) }));
      setEduKeys((keys) => keys.filter((_, i) => i !== index));
    },
    [setProfile],
  );

  const updateEducation = useCallback(
    (index: number, key: keyof ResumeEducationItem, value: string) => {
      setProfile((p) => {
        const educations = [...p.educations];
        educations[index] = { ...educations[index], [key]: value };
        return { ...p, educations };
      });
    },
    [setProfile],
  );

  // ── Server <-> form ───────────────────────────────────────────────────────
  const applyServer = useCallback((server: ResumeProfileResponse) => {
    const normalized = normalizeProfile(server.profile);
    setProfileState(normalized);
    setExpKeys(normalized.experiences.map(() => genKey()));
    setEduKeys(normalized.educations.map(() => genKey()));
    setSelectedTemplateState(server.selected_template || DEFAULT_TEMPLATE);
    setAccentColorState(server.accent_color || DEFAULT_ACCENT);
    dirtyRef.current = false;
    setDirty(false);
  }, []);

  /** Clear the dirty flag when nothing changed since the save went out. */
  const markSynced = useCallback((fingerprint: string, current: string) => {
    if (fingerprint !== current) return;
    dirtyRef.current = false;
    setDirty(false);
  }, []);

  const doc: ResumeDoc = useMemo(
    () => ({ profile, selectedTemplate, accentColor }),
    [profile, selectedTemplate, accentColor],
  );

  const fingerprint = useMemo(() => makeFingerprint(doc), [doc]);

  // ── Restore the local draft once the account is known ──────────────────────
  useEffect(() => {
    if (!userId || restoredRef.current) return;
    restoredRef.current = true;
    const draft = readLocalDraft(userId);
    if (!draft) return;
    localDraftAtRef.current = draft.updatedAt;
    lastPhotoRef.current = draft.profile.photo_url;
    if (!profileHasContent(draft.profile)) return;
    setProfileState(draft.profile);
    setExpKeys(draft.profile.experiences.map(() => genKey()));
    setEduKeys(draft.profile.educations.map(() => genKey()));
    setSelectedTemplateState(draft.selectedTemplate);
    setAccentColorState(draft.accentColor);
    setJobDescriptionState(draft.jobDescription);
    dirtyRef.current = true;
    setDirty(true);
    onRestoredRef.current();
  }, [userId]);

  // ── Persist the draft (debounced, never before the restore attempt) ────────
  useEffect(() => {
    if (!userId || !restoredRef.current) return;
    const timeout = setTimeout(() => {
      localDraftAtRef.current = Date.now();
      lastPhotoRef.current = writeLocalDraft(
        userId,
        {
          profile,
          selectedTemplate,
          accentColor,
          jobDescription,
          updatedAt: localDraftAtRef.current,
        },
        lastPhotoRef.current,
      );
    }, SAVE_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [userId, profile, selectedTemplate, accentColor, jobDescription]);

  return {
    profile,
    selectedTemplate,
    accentColor,
    jobDescription,
    doc,
    fingerprint,
    dirty,
    dirtyRef,
    localDraftAtRef,
    expKeys,
    eduKeys,
    setProfile,
    patchProfile,
    setSelectedTemplate,
    setAccentColor,
    setJobDescription,
    addExperience,
    removeExperience,
    updateExperience,
    appendExperienceBullet,
    addEducation,
    removeEducation,
    updateEducation,
    applyServer,
    markSynced,
    markDirty,
  };
}

export default useResumeDraft;
