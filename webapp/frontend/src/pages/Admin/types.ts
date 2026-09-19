/**
 * Response shapes of the admin endpoints.
 * Mirrors the pydantic models in `webapp/routers/admin_panel.py` and the two
 * admin endpoints of `webapp/routers/wallet.py`.
 */
import type { Lang } from "../../store/lang";


export type AdminState = {
  is_admin: boolean;
  auto_post_enabled: boolean;
  auto_post_channel: string;
  auto_post_min_salary: number;
  auto_post_per_day_min: number;
  auto_post_per_day_max: number;
  /** Language of the auto-post / weekly-stats messages sent to the channel. */
  channel_lang: Lang;
  referral_enabled: boolean;
  referral_required_count: number;
  pro_price: number;
  referral_reward: number;
  pro_min_salary: number;
  resume_target_creation_minutes: number;
  resume_target_completion_rate: number;
  resume_target_send_success_rate: number;
  resume_target_export_success_rate: number;
};

/** The patch body of `PATCH /admin/state` — every field is optional. */
export type AdminStatePatch = Partial<Omit<AdminState, "is_admin">>;

export type AutoPostScheduleItem = {
  ts: number;
  done: boolean;
  uid: string | null;
  /** HH:MM in UTC+5, already formatted by the API. */
  time_str: string;
};

export type AutoPostSchedule = {
  schedule: AutoPostScheduleItem[];
  posted_today: number;
  total_today: number;
};

export type ResumeMetrics = {
  opened_24h: number;
  ready_24h: number;
  save_success_24h: number;
  save_error_24h: number;
  send_success_24h: number;
  send_error_24h: number;
  export_success_24h: number;
  export_error_24h: number;
  unique_users_24h: number;
  avg_ttfi_ms: number;
  avg_save_latency_ms: number;
  avg_send_latency_ms: number;
  avg_export_latency_ms: number;
};

export type ResumeFunnelStep = {
  step: string;
  entered_users: number;
  completed_users: number;
  dropoff_users: number;
  completion_rate: number;
};

export type ResumeFunnel = {
  window_hours: number;
  steps: ResumeFunnelStep[];
};

export type ResumeUserEvent = {
  event_name: string;
  step?: string | null;
  created_at: number;
};

export type ResumeUserInspect = {
  user_id: number;
  first_name: string;
  username: string;
  has_resume: boolean;
  selected_template: string;
  updated_at: number | null;
  profile_preview: Record<string, string | number>;
  recent_events: ResumeUserEvent[];
};

export type ResumeDiagnosticsItem = {
  source: string;
  status: string;
  error_text: string;
  count_24h: number;
  last_seen_at: number;
};

export type ResumeDiagnostics = {
  items: ResumeDiagnosticsItem[];
};

export type ResumeGoals = {
  window_hours: number;
  opened_users: number;
  completed_users: number;
  send_attempts: number;
  pdf_export_attempts: number;
  median_creation_minutes: number;
  completion_rate: number;
  send_success_rate: number;
  pdf_export_success_rate: number;
  creation_time_target_minutes: number;
  completion_rate_target: number;
  send_success_rate_target: number;
  pdf_export_success_rate_target: number;
  creation_time_ok: boolean;
  completion_rate_ok: boolean;
  send_success_rate_ok: boolean;
  pdf_export_success_rate_ok: boolean;
};

export type AddBalanceResult = {
  ok: boolean;
  new_balance: number;
};

export type ResetUserResult = {
  ok: boolean;
  user_id: number;
};
