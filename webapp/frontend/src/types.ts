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

/** `data.normalized` of `GET /jobs/{uid}`: localized labels plus raw `codes`. */
export type VacancyNormalized = Record<string, unknown> & {
  codes?: VacancyCodes;
};

/** `GET /jobs/{uid}` response. */
export type VacancyDetailResponse = {
  uid: string;
  data: Record<string, unknown> & { normalized?: VacancyNormalized };
};
