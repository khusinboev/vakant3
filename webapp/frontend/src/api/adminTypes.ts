/**
 * Request/response types for every `/api/admin/*` (and `/api/wallet/*` admin)
 * endpoint. Field names mirror the backend exactly — see CONTRACT_P0.md /
 * CONTRACT_P12.md and, where the router already exists,
 * `webapp/routers/{admin_panel,admin_admins,wallet,admin_finance}.py` and the
 * `src/db/migrations/m00[2-9]_*.py` schemas.
 *
 * Endpoints for Content, Broadcasts, Users, Auto-post, Analytics and System
 * (CONTRACT_P12.md) are not implemented on the backend yet at the time this
 * file was written — those types are modeled directly from the contract's
 * schema section. Ambiguities are called out per-section below and in the
 * hand-off report.
 */
import type { AdminState, AdminStatePatch } from "../pages/Admin/types";

/** Ordered least to most privileged, matches `webapp/core/auth.py:ROLES`. */
export type AdminRole = "owner" | "admin" | "moderator" | "viewer";

/** Generic cursor page shape used by every P12 list endpoint. */
export type CursorPage<T> = {
  items: T[];
  next_cursor: string | null;
  total: number | null;
};

// ---------------------------------------------------------------------------
// Settings (state) — GET/PATCH /admin/state
// ---------------------------------------------------------------------------

/** `GET /admin/state` response: the existing `AdminState` plus role + optimistic-lock version. */
export type AdminStateV2 = AdminState & {
  role: AdminRole;
  version: number;
};

/** `PATCH /admin/state` body: the existing patch plus an optional version guard. */
export type AdminStatePatchBody = AdminStatePatch & {
  /** When set and stale, the API returns 409 SETTINGS_CONFLICT{version}. */
  expected_version?: number;
};

// ---------------------------------------------------------------------------
// Confirmation tokens — POST /admin/confirm
// ---------------------------------------------------------------------------

export type ConfirmRequestBody = {
  action: string;
  params: Record<string, unknown>;
};

export type ConfirmResponse = {
  token: string;
  expires_in: number;
};

// ---------------------------------------------------------------------------
// Admins roster — /admin/admins (owner only)
// ---------------------------------------------------------------------------

export type AdminRow = {
  user_id: number;
  role: AdminRole;
  added_by: number | null;
  added_at: number;
  disabled: boolean;
  first_name: string;
  username: string;
};

export type AdminListResponse = { items: AdminRow[] };

export type AdminCreateBody = { user_id: number; role: AdminRole };

export type AdminUpdateBody = { role?: AdminRole; disabled?: boolean };

// ---------------------------------------------------------------------------
// Wallet (P0, already implemented) — /wallet/*
// ---------------------------------------------------------------------------

export type WalletTransactionKind =
  | "pro_activation"
  | "referral_reward"
  | "admin_credit"
  | "admin_reset"
  | "adjustment";

export type WalletTransactionItem = {
  id: number;
  kind: WalletTransactionKind;
  amount: number;
  balance_after: number;
  price_snapshot: number | null;
  note: string | null;
  created_at: number;
};

/**
 * `GET /wallet/transactions` does NOT use the P12 cursor shape (no `total`,
 * and the cursor is the raw last row id, not an opaque string) — it predates
 * CONTRACT_P12 and is kept as-is (see webapp/routers/wallet.py).
 */
export type WalletTransactionsResponse = {
  items: WalletTransactionItem[];
  next_cursor: number | null;
};

export type AdminAddBalanceBody = { user_id: number; amount: number; note?: string };
export type AdminAddBalanceResponse = { ok: boolean; new_balance: number; tx_id: number };

export type AdminResetUserBody = { user_id: number; note?: string };
export type AdminResetUserResponse = {
  ok: boolean;
  user_id: number;
  new_balance: number;
  tx_id: number;
};

// ---------------------------------------------------------------------------
// Channels — /admin/channels (m006_entry_gate schema)
// ---------------------------------------------------------------------------

export type Channel = {
  id: string;
  title: string | null;
  username: string | null;
  invite_link: string | null;
  chat_id: number | null;
  enabled: boolean;
  added_by: number | null;
  added_at: number | null;
  last_check_ok: boolean | null;
  last_check_at: number | null;
};

/** Channel list is small and flat, not cursor-paginated (webapp/routers/admin_channels.py). */
export type ChannelListResponse = { items: Channel[] };

export type ChannelCreateBody = {
  link: string;
  /** Required when `link` is a private `t.me/+hash` invite (getChat cannot resolve those). */
  chat_id?: number;
};

export type ChannelCreateResult = { channel: Channel; status: string };
export type ChannelPatchBody = { enabled: boolean };
export type ChannelPatchResult = { ok: boolean; id: string; enabled: boolean };
export type ChannelDeleteResult = { ok: boolean; id: string };
export type ChannelCheckResult = { id: string; ok: boolean; status: string; detail: string | null };

// ---------------------------------------------------------------------------
// Content — /admin/content/{articles,tips,categories}
// (webapp/routers/admin_content.py + webapp/core/content_repo.py — every
// multilingual field is a nested {uz, ru?, en?} object, NOT flat `_uz/_ru/_en`
// keys; `ru`/`en` are omitted entirely when empty, `uz` is always present.
// `updated_at`/`updated_by` are DB bookkeeping only and never come back in a
// response.)
// ---------------------------------------------------------------------------

export type LocalizedText = { uz: string; ru?: string; en?: string };

export type ContentCategory = {
  id: string;
  sort_order: number;
  name: LocalizedText;
};

export type ContentArticleAdmin = {
  id: string;
  category_id: string;
  sort_order: number;
  published: boolean;
  source_url: string;
  title: LocalizedText;
  summary: LocalizedText;
  full_text: LocalizedText;
  source_label: LocalizedText;
};

export type ContentTipAdmin = {
  id: string;
  sort_order: number;
  published: boolean;
  title: LocalizedText;
  summary: LocalizedText;
  full_text: LocalizedText;
};

/** Admin content lists are small and flat, not cursor-paginated. */
export type ContentArticleListResponse = { items: ContentArticleAdmin[] };
export type ContentTipListResponse = { items: ContentTipAdmin[] };
export type ContentCategoryListResponse = { items: ContentCategory[] };

/** `PUT` body (no `id`, it comes from the URL); `category_id` required for articles. */
export type ContentArticleUpdateBody = Omit<ContentArticleAdmin, "id">;
/** `POST` (create) body: the update body plus the new slug `id`. */
export type ContentArticleCreateBody = ContentArticleUpdateBody & { id: string };

export type ContentTipUpdateBody = Omit<ContentTipAdmin, "id">;
export type ContentTipCreateBody = ContentTipUpdateBody & { id: string };

export type ContentCategoryUpdateBody = Omit<ContentCategory, "id">;
export type ContentCategoryCreateBody = ContentCategoryUpdateBody & { id: string };

// ---------------------------------------------------------------------------
// Broadcasts — /admin/broadcasts, /admin/uploads (m008_broadcasts schema)
// ---------------------------------------------------------------------------

export type BroadcastStatus =
  | "draft"
  | "queued"
  | "running"
  | "paused"
  | "cancelled"
  | "done"
  | "failed";

export type BroadcastKind = "text" | "photo" | "video" | "document" | "forward";

export type BroadcastButton = { text: string; url: string };

/** `segment` matches CONTRACT_P12.md's targeting grammar; kept as `string` for forward-compat. */
export type BroadcastTargetSpec = {
  segment: "all" | "pro" | "free" | "test_admins" | string;
  exclude_blocked?: boolean;
};

/**
 * The DB stores `buttons_json`/`target_json` as TEXT; `webapp/routers/admin_broadcasts.py`'s
 * `_row_to_dict` parses them into `buttons`/`target` objects on every read.
 */
export type Broadcast = {
  id: number;
  actor_id: number;
  status: BroadcastStatus;
  kind: BroadcastKind;
  text: string | null;
  parse_mode: string | null;
  media_path: string | null;
  media_file_id: string | null;
  forward_chat_id: number | null;
  forward_message_id: number | null;
  buttons: BroadcastButton[];
  target: BroadcastTargetSpec;
  total: number;
  sent: number;
  failed: number;
  blocked: number;
  error: string | null;
  created_at: number | null;
  started_at: number | null;
  finished_at: number | null;
};

export type BroadcastTargetError = {
  user_id: number;
  status: string;
  error: string | null;
  sent_at: number | null;
};

/** `GET /admin/broadcasts/{id}`: the row plus its last 20 target errors and a status breakdown. */
export type BroadcastDetail = Broadcast & {
  errors: BroadcastTargetError[];
  targets: Record<string, number>;
  text_preview: string;
};

/**
 * Flat, not nested under `target`: matches `BroadcastCreateIn` in
 * `webapp/routers/admin_broadcasts.py` exactly. `webapp/core/confirm.py`'s
 * `require_confirmation` binds a token only to TOP-LEVEL JSON body keys
 * (`body.get(key)`), and the create endpoint's confirmation
 * (`broadcast.create`, [kind, segment]) needs `segment` reachable that way —
 * confirmed against the real router, not just the contract text.
 */
export type BroadcastCreateBody = {
  kind: BroadcastKind;
  text?: string;
  buttons?: BroadcastButton[];
  media_path?: string;
  forward_chat_id?: number;
  forward_message_id?: number;
  segment?: BroadcastTargetSpec["segment"];
  exclude_blocked?: boolean;
};

export type BroadcastQueueResult = { id: number; status: BroadcastStatus; total: number };
export type BroadcastPreviewResult = { ok: boolean; message_id: number | null };
export type BroadcastCancelResult = { id: number; status: BroadcastStatus };
export type UploadResult = { path: string; mime: string; size: number; kind: string };

// ---------------------------------------------------------------------------
// Users — /admin/users (webapp/routers/admin_users.py)
// ---------------------------------------------------------------------------

export type AdminUserListItem = {
  user_id: number;
  username: string | null;
  first_name: string | null;
  lang: string | null;
  date: number | null;
  region: string | null;
  district: string | null;
  is_pro: boolean;
  pro_until: number | null;
  balance: number;
  banned: boolean;
  banned_reason: string | null;
  blocked: boolean;
  last_seen_at: number | null;
  ref_by: number | null;
};

export type AdminUsersQuery = {
  q?: string;
  pro?: boolean;
  banned?: boolean;
  blocked?: boolean;
  lang?: string;
  region?: string;
  from?: number;
  to?: number;
  sort?: "date" | "balance" | "last_seen";
  limit?: number;
  cursor?: string;
};

export type AdminUserWallet = { balance: number; is_pro: boolean; pro_until: number | null };

export type AdminUserCounts = {
  saves: number;
  referrals: number;
  payouts_sum: number;
  resume_exports: number;
};

/** Raw `wallet_transactions` row incl. `actor_id` — same fields as `FinanceTransactionItem`. */
export type AdminUserTransaction = FinanceTransactionItem;

export type AdminUserEvent = {
  id: number;
  event_name: string;
  step: string | null;
  created_at: number;
};

export type AdminUserNotificationSettings = {
  enabled: boolean;
  created_at: number;
  updated_at: number;
};

export type AdminUserReferrer = {
  user_id: number;
  first_name: string | null;
  username: string | null;
};

export type AdminUserDetail = {
  user: AdminUserListItem;
  wallet: AdminUserWallet;
  counts: AdminUserCounts;
  recent_transactions: AdminUserTransaction[];
  recent_events: AdminUserEvent[];
  notification_settings: AdminUserNotificationSettings | null;
  referrer: AdminUserReferrer | null;
};

export type AdminUserSaveItem = { save_id: number | string; uid: string };

export type SetProBody = { enabled: boolean; days?: number | null; note?: string };
export type SetProResult = {
  ok: boolean;
  user_id: number;
  is_pro: boolean;
  pro_until: number | null;
  tx_id: number | null;
};

export type AdminUserBalanceBody = { amount: number; note?: string };
export type AdminUserBalanceResult = {
  ok: boolean;
  user_id: number;
  amount: number;
  new_balance: number;
  tx_id: number;
};

export type BanUserBody = { banned: boolean; reason?: string };
export type BanUserResult = { ok: boolean; user_id: number; banned: boolean; reason: string | null };

export type MessageUserBody = { text: string };
export type MessageUserResult = { ok: boolean; user_id: number; message_id: number | null };

export type AdminActionOkResponse = { ok: boolean };

// ---------------------------------------------------------------------------
// Auto-post — /admin/auto-post/*, /admin/jobs/{id} (webapp/routers/admin_autopost.py)
// ---------------------------------------------------------------------------

export type AutoPostLogStatus = "sent" | "failed" | "skipped";

export type AutoPostLogItem = {
  id: number;
  uid: string | null;
  channel: string | null;
  message_id: number | null;
  status: AutoPostLogStatus;
  error: string | null;
  posted_at: number;
};

export type PostNowBody = { uid?: string };
export type PostNowResult = { job_id: number; status: string };

export type BotJobStatus = "queued" | "running" | "done" | "failed";

/** `GET /admin/jobs/{id}` response — `result_json` is parsed into `result`; no `payload`/`created_by`. */
export type BotJob = {
  id: number;
  kind: string;
  status: BotJobStatus;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
};

// ---------------------------------------------------------------------------
// Finance — /admin/finance/* (already implemented, webapp/routers/admin_finance.py)
// ---------------------------------------------------------------------------

export type FinanceTotals = {
  revenue: number;
  activations: number;
  admin_credits: number;
  referral_payouts: number;
  balance_outstanding: number;
};

export type FinanceSeriesPoint = {
  day: string;
  revenue: number;
  activations: number;
  payouts: number;
};

export type FinanceSummary = { totals: FinanceTotals; series: FinanceSeriesPoint[] };

export type FinanceTransactionItem = {
  id: number;
  user_id: number;
  kind: WalletTransactionKind;
  amount: number;
  balance_after: number;
  price_snapshot: number | null;
  actor_id: number | null;
  note: string | null;
  created_at: number;
};

export type FinanceTransactionsQuery = {
  kind?: WalletTransactionKind;
  user_id?: number;
  from?: number;
  to?: number;
  limit?: number;
  cursor?: string;
};

export type FinanceReferralItem = {
  inviter_id: number;
  inviter_name: string;
  invited_count: number;
  paid_sum: number;
};

// ---------------------------------------------------------------------------
// Analytics — /admin/analytics/overview (webapp/routers/admin_analytics.py)
// ---------------------------------------------------------------------------

export type DailyStatsPoint = {
  day: string;
  new_users: number;
  active_users: number;
  pro_users: number;
  pro_activations: number;
  revenue: number;
  referral_payouts: number;
  saves: number;
  resume_saves: number;
  resume_sends_ok: number;
  resume_sends_err: number;
  auto_posts: number;
  notifications: number;
  broadcasts_sent: number;
  computed_at: number;
};

export type AnalyticsOverview = {
  days: number;
  /** Persisted, completed days only (`daily_stats`). */
  series: DailyStatsPoint[];
  /** Computed live on every call (`src/functions/daily_rollup.py:compute_day`); never persisted. */
  today: Omit<DailyStatsPoint, "computed_at">;
};

// ---------------------------------------------------------------------------
// System — /admin/system, /admin/errors, /admin/audit (webapp/routers/admin_system.py)
// ---------------------------------------------------------------------------

export type SystemInfo = {
  db: { size_bytes: number; wal_bytes: number; page_count: number };
  counts: { users: number; sessions: number; resume_events: number; broadcasts_running: number };
  schedulers: {
    auto_post: { last_run: number | null; scheduled_day: string | null; next_slots: unknown[] };
    notifications: { last_run: number | null };
    weekly_stats: { last_week: string | null };
  };
  redis: boolean;
  version: string | null;
  uptime: number;
};

export type ErrorLogSource = "api" | "bot" | "scheduler";

export type ErrorLogItem = {
  id: number;
  created_at: number;
  source: ErrorLogSource;
  level: string;
  message: string;
  context: Record<string, unknown> | null;
};

export type ErrorLogQuery = { limit?: number; cursor?: string; source?: ErrorLogSource };

export type AuditLogItem = {
  id: number;
  created_at: number;
  actor_id: number;
  action: string;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, unknown> | null;
  ip: string | null;
};

export type AuditLogQuery = { actor?: number; action?: string; limit?: number; cursor?: string };
