export type UserProfile = {
  user_id: number;
  first_name: string;
  username: string | null;
  photo_url: string | null;
  lang: string;
};

export type VacancyItem = {
  uid: string;
  title: string;
  company: string;
  /** Localized by the API; null when the source has no salary information. */
  salary_text: string | null;
  location: string | null;
  district: string | null;
  posted_at: string | null;
  is_saved: boolean;
  is_pro_locked: boolean;
  /** Vacancy store source (`osonish` | `hh`), its display name and the original posting URL. */
  source?: string;
  source_label?: string | null;
  url?: string | null;
  /** Open vacancies collapsed into this card by dedup (1 when alone). */
  openings?: number;
};

/** Raw integer codes from osonish.uz — render them with `useVacancyCodeLabel`. */
export type VacancyCodes = {
  gender?: number | null;
  work_type?: number | null;
  busyness_type?: number | null;
  payment_type?: number | null;
  education?: number | null;
  experience?: number | null;
};

/** Raw hh.uz dictionary ids — render them with the `vacancy.hh.*` maps. */
export type VacancyHhCodes = {
  experience?: string;
  employment?: string;
  schedule?: string;
};

/** `data.normalized` of `GET /jobs/{uid}`: localized labels plus raw `codes`. */
export type VacancyNormalized = Record<string, unknown> & {
  codes?: VacancyCodes;
  hh_codes?: VacancyHhCodes;
  source?: string;
  source_label?: string;
  url?: string;
};

/** `GET /jobs/{uid}` response. */
export type VacancyDetailResponse = {
  uid: string;
  data: Record<string, unknown> & { normalized?: VacancyNormalized };
};
