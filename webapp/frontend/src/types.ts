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
  salary_text: string;
  location: string;
  district: string;
  posted_at: string;
  is_saved: boolean;
  is_pro_locked: boolean;
};

export type VacancyDetail = {
  uid: string;
  data: Record<string, unknown>;
};
