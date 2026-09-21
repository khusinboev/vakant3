/**
 * Typed client for every `/api/admin/*` endpoint plus the two admin-only
 * `/api/wallet/*` endpoints. One function per endpoint, named exports only
 * (tree-shakeable). No React and no UI here — see CONTRACT_UI.md.
 *
 * Every endpoint below is typed against the real backend code, read directly
 * from the routers as they landed while this file was written:
 * `webapp/routers/{admin_panel,admin_admins,wallet,admin_finance,
 * admin_channels,admin_content,admin_broadcasts,admin_users,admin_autopost,
 * admin_analytics,admin_system}.py` and `webapp/core/{content_repo,uploads}.py`.
 * Where a router hadn't landed yet, CONTRACT_P12.md's schema section was used
 * instead — none remained by the time this file was finished.
 */
import client from "./client";
import type {
  AdminActionOkResponse,
  AdminAddBalanceBody,
  AdminAddBalanceResponse,
  AdminCreateBody,
  AdminListResponse,
  AdminResetUserBody,
  AdminResetUserResponse,
  AdminRow,
  AdminStatePatchBody,
  AdminStateV2,
  AdminUpdateBody,
  AdminUserBalanceBody,
  AdminUserBalanceResult,
  AdminUserDetail,
  AdminUserListItem,
  AdminUserSaveItem,
  AdminUsersQuery,
  AnalyticsOverview,
  AuditLogItem,
  AuditLogQuery,
  AutoPostLogItem,
  BanUserBody,
  BanUserResult,
  BotJob,
  Broadcast,
  BroadcastCancelResult,
  BroadcastCreateBody,
  BroadcastDetail,
  BroadcastPreviewResult,
  BroadcastQueueResult,
  ChannelCheckResult,
  ChannelCreateBody,
  ChannelCreateResult,
  ChannelDeleteResult,
  ChannelListResponse,
  ChannelPatchBody,
  ChannelPatchResult,
  ConfirmResponse,
  ContentArticleAdmin,
  ContentArticleCreateBody,
  ContentArticleListResponse,
  ContentArticleUpdateBody,
  ContentCategory,
  ContentCategoryCreateBody,
  ContentCategoryListResponse,
  ContentCategoryUpdateBody,
  ContentTipAdmin,
  ContentTipCreateBody,
  ContentTipListResponse,
  ContentTipUpdateBody,
  CursorPage,
  ErrorLogItem,
  ErrorLogQuery,
  FinanceReferralItem,
  FinanceSummary,
  FinanceTransactionItem,
  FinanceTransactionsQuery,
  MessageUserBody,
  MessageUserResult,
  PostNowBody,
  PostNowResult,
  SetProBody,
  SetProResult,
  SystemInfo,
  UploadResult,
  WalletTransactionsResponse,
} from "./adminTypes";

// ---------------------------------------------------------------------------
// Query-key helpers. Convention (CONTRACT_UI.md): ["admin", <area>, ...params],
// invalidate by prefix ["admin", <area>].
// ---------------------------------------------------------------------------

export const adminKeys = {
  admins: () => ["admin", "admins"] as const,
  state: () => ["admin", "state"] as const,
  channels: () => ["admin", "channels"] as const,
  users: (query?: AdminUsersQuery) => ["admin", "users", query ?? {}] as const,
  userDetail: (userId: number) => ["admin", "users", "detail", userId] as const,
  userSaves: (userId: number, cursor?: string) =>
    ["admin", "users", "saves", userId, cursor ?? null] as const,
  contentArticles: () => ["admin", "content-articles"] as const,
  contentArticle: (id: string) => ["admin", "content-articles", id] as const,
  contentTips: () => ["admin", "content-tips"] as const,
  contentCategories: () => ["admin", "content-categories"] as const,
  broadcasts: (cursor?: string) => ["admin", "broadcasts", cursor ?? null] as const,
  broadcastDetail: (id: number) => ["admin", "broadcasts", "detail", id] as const,
  autoPostHistory: (cursor?: string) => ["admin", "auto-post-history", cursor ?? null] as const,
  job: (id: number) => ["admin", "jobs", id] as const,
  financeSummary: (days: number) => ["admin", "finance-summary", days] as const,
  financeTransactions: (query?: FinanceTransactionsQuery) =>
    ["admin", "finance-transactions", query ?? {}] as const,
  financeReferrals: (cursor?: string) => ["admin", "finance-referrals", cursor ?? null] as const,
  analyticsOverview: (days: number) => ["admin", "analytics-overview", days] as const,
  system: () => ["admin", "system"] as const,
  errors: (cursor?: string) => ["admin", "errors", cursor ?? null] as const,
  audit: (query?: AuditLogQuery) => ["admin", "audit", query ?? {}] as const,
};

// ---------------------------------------------------------------------------
// Confirmation tokens (webapp/core/confirm.py)
// ---------------------------------------------------------------------------

/**
 * Mints a short-lived (60 s) confirmation token bound to this exact action and
 * parameter set (`POST /api/admin/confirm`). `params` must match, key for
 * key, what the confirmed request's JSON body will carry for those keys —
 * `require_confirmation` on the backend recomputes the MAC from the real
 * request body and rejects a mismatch.
 */
export async function confirmAction(action: string, params: Record<string, unknown>): Promise<string> {
  const { data } = await client.post<ConfirmResponse>("/admin/confirm", { action, params });
  return data.token;
}

/**
 * Mints a confirmation token for `action`/`params`, then calls `fn` with the
 * `X-Confirm-Token` header to inject into the real (confirmed) request.
 */
export async function withConfirm<R>(
  action: string,
  params: Record<string, unknown>,
  fn: (headers: { "X-Confirm-Token": string }) => Promise<R>
): Promise<R> {
  const token = await confirmAction(action, params);
  return fn({ "X-Confirm-Token": token });
}

// ---------------------------------------------------------------------------
// Settings (state) — GET/PATCH /admin/state
// ---------------------------------------------------------------------------

/** Full admin settings singleton, including `role` and the optimistic-lock `version`. */
export async function getAdminState(): Promise<AdminStateV2> {
  return (await client.get<AdminStateV2>("/admin/state")).data;
}

/** Patches the settings singleton; pass `expected_version` to get 409 SETTINGS_CONFLICT on a stale write. */
export async function patchAdminState(body: AdminStatePatchBody): Promise<AdminStateV2> {
  return (await client.patch<AdminStateV2>("/admin/state", body)).data;
}

// ---------------------------------------------------------------------------
// Admins roster (owner only) — /admin/admins
// ---------------------------------------------------------------------------

/** Lists every admin row, including disabled ones. */
export async function listAdmins(): Promise<AdminListResponse> {
  return (await client.get<AdminListResponse>("/admin/admins")).data;
}

/** Adds (or revives a disabled) admin with the given role. */
export async function addAdmin(body: AdminCreateBody): Promise<AdminRow> {
  return (await client.post<AdminRow>("/admin/admins", body)).data;
}

/** Changes an admin's role and/or disabled flag. */
export async function updateAdmin(userId: number, body: AdminUpdateBody): Promise<AdminRow> {
  return (await client.patch<AdminRow>(`/admin/admins/${userId}`, body)).data;
}

/** Removes an admin outright (refused if they are the last enabled owner). */
export async function removeAdmin(userId: number): Promise<AdminActionOkResponse> {
  return (await client.delete<AdminActionOkResponse>(`/admin/admins/${userId}`)).data;
}

// ---------------------------------------------------------------------------
// Wallet (own history + admin mutations) — /wallet/*
// ---------------------------------------------------------------------------

/** The caller's own ledger history, newest first (`before_id` cursor, NOT the P12 cursor shape). */
export async function getWalletTransactions(params?: {
  before_id?: number;
  limit?: number;
}): Promise<WalletTransactionsResponse> {
  return (await client.get<WalletTransactionsResponse>("/wallet/transactions", { params })).data;
}

/** Admin: credits a user's balance. Requires confirmation (`wallet.add_balance`, [user_id, amount]). */
export async function adminAddBalance(body: AdminAddBalanceBody): Promise<AdminAddBalanceResponse> {
  return withConfirm(
    "wallet.add_balance",
    { user_id: body.user_id, amount: body.amount },
    async (headers) =>
      (await client.post<AdminAddBalanceResponse>("/wallet/admin/add-balance", body, { headers })).data
  );
}

/** Admin: zeroes a user's balance and drops Pro. Requires confirmation (`wallet.reset_user`, [user_id]). */
export async function adminResetUser(body: AdminResetUserBody): Promise<AdminResetUserResponse> {
  return withConfirm(
    "wallet.reset_user",
    { user_id: body.user_id },
    async (headers) =>
      (await client.post<AdminResetUserResponse>("/wallet/admin/reset-user", body, { headers })).data
  );
}

// ---------------------------------------------------------------------------
// Channels — /admin/channels
// ---------------------------------------------------------------------------

/** Lists every subscription-gate channel (enabled and disabled). */
export async function listChannels(): Promise<ChannelListResponse> {
  return (await client.get<ChannelListResponse>("/admin/channels")).data;
}

/** Adds a channel by @username, t.me link, invite link or -100 chat id; validated server-side. */
export async function addChannel(body: ChannelCreateBody): Promise<ChannelCreateResult> {
  return (await client.post<ChannelCreateResult>("/admin/channels", body)).data;
}

/** Enables/disables a channel in the subscription gate. */
export async function patchChannel(id: string, body: ChannelPatchBody): Promise<ChannelPatchResult> {
  return (await client.patch<ChannelPatchResult>(`/admin/channels/${encodeURIComponent(id)}`, body))
    .data;
}

/** Removes a channel from the gate. */
export async function deleteChannel(id: string): Promise<ChannelDeleteResult> {
  return (await client.delete<ChannelDeleteResult>(`/admin/channels/${encodeURIComponent(id)}`)).data;
}

/** Re-checks a channel's bot-is-admin status immediately. */
export async function checkChannel(id: string): Promise<ChannelCheckResult> {
  return (await client.post<ChannelCheckResult>(`/admin/channels/${encodeURIComponent(id)}/check`)).data;
}

// ---------------------------------------------------------------------------
// Content — /admin/content/{articles,tips,categories}
// ---------------------------------------------------------------------------

/** Lists every law article, including unpublished ones. */
export async function listContentArticles(): Promise<ContentArticleListResponse> {
  return (await client.get<ContentArticleListResponse>("/admin/content/articles")).data;
}

/** Reads one article by id. */
export async function getContentArticle(id: string): Promise<ContentArticleAdmin> {
  return (await client.get<ContentArticleAdmin>(`/admin/content/articles/${encodeURIComponent(id)}`)).data;
}

/** Creates a new article (`body.id` is the new slug). */
export async function createContentArticle(body: ContentArticleCreateBody): Promise<ContentArticleAdmin> {
  return (await client.post<ContentArticleAdmin>("/admin/content/articles", body)).data;
}

/** Replaces an article's full multilingual body (`id` comes from the URL, not the body). */
export async function updateContentArticle(
  id: string,
  body: ContentArticleUpdateBody
): Promise<ContentArticleAdmin> {
  return (await client.put<ContentArticleAdmin>(`/admin/content/articles/${encodeURIComponent(id)}`, body))
    .data;
}

/** Deletes an article. */
export async function deleteContentArticle(id: string): Promise<AdminActionOkResponse> {
  return (
    await client.delete<AdminActionOkResponse>(`/admin/content/articles/${encodeURIComponent(id)}`)
  ).data;
}

/** Lists every HR tip, including unpublished ones. */
export async function listContentTips(): Promise<ContentTipListResponse> {
  return (await client.get<ContentTipListResponse>("/admin/content/tips")).data;
}

/** Reads one HR tip by id. */
export async function getContentTip(id: string): Promise<ContentTipAdmin> {
  return (await client.get<ContentTipAdmin>(`/admin/content/tips/${encodeURIComponent(id)}`)).data;
}

/** Creates a new HR tip (`body.id` is the new slug). */
export async function createContentTip(body: ContentTipCreateBody): Promise<ContentTipAdmin> {
  return (await client.post<ContentTipAdmin>("/admin/content/tips", body)).data;
}

/** Replaces an HR tip's full multilingual body (`id` comes from the URL, not the body). */
export async function updateContentTip(id: string, body: ContentTipUpdateBody): Promise<ContentTipAdmin> {
  return (await client.put<ContentTipAdmin>(`/admin/content/tips/${encodeURIComponent(id)}`, body)).data;
}

/** Deletes an HR tip. */
export async function deleteContentTip(id: string): Promise<AdminActionOkResponse> {
  return (await client.delete<AdminActionOkResponse>(`/admin/content/tips/${encodeURIComponent(id)}`)).data;
}

/** Lists every content category. */
export async function listContentCategories(): Promise<ContentCategoryListResponse> {
  return (await client.get<ContentCategoryListResponse>("/admin/content/categories")).data;
}

/** Creates a new content category (`body.id` is the new slug). */
export async function createContentCategory(body: ContentCategoryCreateBody): Promise<ContentCategory> {
  return (await client.post<ContentCategory>("/admin/content/categories", body)).data;
}

/** Updates a content category's names/sort order (`id` comes from the URL, not the body). */
export async function updateContentCategory(
  id: string,
  body: ContentCategoryUpdateBody
): Promise<ContentCategory> {
  return (await client.put<ContentCategory>(`/admin/content/categories/${encodeURIComponent(id)}`, body))
    .data;
}

/** Deletes a content category. */
export async function deleteContentCategory(id: string): Promise<AdminActionOkResponse> {
  return (
    await client.delete<AdminActionOkResponse>(`/admin/content/categories/${encodeURIComponent(id)}`)
  ).data;
}

// ---------------------------------------------------------------------------
// Broadcasts + uploads — /admin/broadcasts, /admin/uploads
// ---------------------------------------------------------------------------

/**
 * Uploads broadcast media (jpg/png/webp/mp4/pdf/docx, <=20MB) as multipart
 * form data. The returned `path` is passed back as `media_path` when creating
 * the broadcast.
 */
export async function uploadBroadcastMedia(file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return (await client.post<UploadResult>("/admin/uploads", form)).data;
}

/**
 * Creates a broadcast as a draft. Requires confirmation (`broadcast.create`,
 * [kind, segment]) — `segment` is read from the top-level request body
 * (`webapp/core/confirm.py`'s `require_confirmation` only binds top-level
 * JSON keys), so this body is intentionally flat rather than nesting
 * `segment`/`exclude_blocked` under a `target` object.
 */
export async function createBroadcast(body: BroadcastCreateBody): Promise<Broadcast> {
  return withConfirm(
    "broadcast.create",
    { kind: body.kind, segment: body.segment },
    async (headers) => (await client.post<Broadcast>("/admin/broadcasts", body, { headers })).data
  );
}

/** Sends the broadcast to the actor only, as a preview. */
export async function previewBroadcast(id: number): Promise<BroadcastPreviewResult> {
  return (await client.post<BroadcastPreviewResult>(`/admin/broadcasts/${id}/preview`)).data;
}

/** Materializes the target list and flips the broadcast to `queued`. */
export async function queueBroadcast(id: number): Promise<BroadcastQueueResult> {
  // Queueing fans out to every target, so it is confirm-token protected (`broadcast.queue`).
  return withConfirm("broadcast.queue", { broadcast_id: id }, async (headers) => {
    const { data } = await client.post<BroadcastQueueResult>(
      `/admin/broadcasts/${id}/queue`,
      { broadcast_id: id },
      { headers },
    );
    return data;
  });
}

/** Cancels a draft/queued/running/paused broadcast at the next batch boundary. No confirmation. */
export async function cancelBroadcast(id: number): Promise<BroadcastCancelResult> {
  return (await client.post<BroadcastCancelResult>(`/admin/broadcasts/${id}/cancel`)).data;
}

/** Lists broadcasts, newest first. */
export async function listBroadcasts(params?: {
  limit?: number;
  cursor?: string;
}): Promise<CursorPage<Broadcast>> {
  return (await client.get<CursorPage<Broadcast>>("/admin/broadcasts", { params })).data;
}

/** Reads one broadcast with its send counters and last 20 target errors. */
export async function getBroadcast(id: number): Promise<BroadcastDetail> {
  return (await client.get<BroadcastDetail>(`/admin/broadcasts/${id}`)).data;
}

// ---------------------------------------------------------------------------
// Users — /admin/users
// ---------------------------------------------------------------------------

/** Filters/searches users; `q` matches user_id exactly or username/first_name via LIKE. */
export async function listAdminUsers(query?: AdminUsersQuery): Promise<CursorPage<AdminUserListItem>> {
  return (await client.get<CursorPage<AdminUserListItem>>("/admin/users", { params: query })).data;
}

/** Full profile: wallet, counts, recent transactions/events, notification settings, referrer. */
export async function getAdminUser(userId: number): Promise<AdminUserDetail> {
  return (await client.get<AdminUserDetail>(`/admin/users/${userId}`)).data;
}

/** Grants or revokes Pro, optionally time-boxed (`days`). No confirmation. */
export async function setUserPro(userId: number, body: SetProBody): Promise<SetProResult> {
  return (await client.post<SetProResult>(`/admin/users/${userId}/pro`, body)).data;
}

/**
 * Credits/debits a user's balance directly (ledger kind `admin_credit`).
 * Requires confirmation (`users.balance`, [user_id, amount]). The wire body
 * carries `user_id` alongside the path id — `BalanceRequest` in
 * `webapp/routers/admin_users.py` requires both to agree, and the token is
 * bound to the top-level `user_id` body key.
 */
export async function setUserBalance(
  userId: number,
  body: AdminUserBalanceBody
): Promise<AdminUserBalanceResult> {
  const fullBody = { user_id: userId, amount: body.amount, note: body.note };
  return withConfirm(
    "users.balance",
    { user_id: userId, amount: body.amount },
    async (headers) =>
      (
        await client.post<AdminUserBalanceResult>(`/admin/users/${userId}/balance`, fullBody, { headers })
      ).data
  );
}

/** Bans or unbans a user (enforced by the entry gate). No confirmation. */
export async function banUser(userId: number, body: BanUserBody): Promise<BanUserResult> {
  return (await client.post<BanUserResult>(`/admin/users/${userId}/ban`, body)).data;
}

/** Sends a direct Telegram message to the user from the panel. No confirmation. */
export async function messageUser(userId: number, body: MessageUserBody): Promise<MessageUserResult> {
  return (await client.post<MessageUserResult>(`/admin/users/${userId}/message`, body)).data;
}

/** The user's saved vacancies, newest first. */
export async function getUserSaves(
  userId: number,
  params?: { limit?: number; cursor?: string }
): Promise<CursorPage<AdminUserSaveItem>> {
  return (await client.get<CursorPage<AdminUserSaveItem>>(`/admin/users/${userId}/saves`, { params }))
    .data;
}

// ---------------------------------------------------------------------------
// Auto-post — /admin/auto-post/*, /admin/jobs/{id}
// ---------------------------------------------------------------------------

/** Every auto-post attempt (sent/failed/skipped), newest first; filterable by channel/status. */
export async function getAutoPostHistory(params?: {
  limit?: number;
  cursor?: string;
  channel?: string;
  status?: AutoPostLogItem["status"];
}): Promise<CursorPage<AutoPostLogItem>> {
  return (await client.get<CursorPage<AutoPostLogItem>>("/admin/auto-post/history", { params })).data;
}

/** Queues an immediate post (optionally a specific `uid`). Requires confirmation (`autopost.post_now`, []). */
export async function postAutoPostNow(body: PostNowBody = {}): Promise<PostNowResult> {
  return withConfirm("autopost.post_now", {}, async (headers) =>
    (await client.post<PostNowResult>("/admin/auto-post/post-now", body, { headers })).data
  );
}

/** Polls a generic bot job's status/result (e.g. the one `postAutoPostNow` returns). */
export async function getBotJob(id: number): Promise<BotJob> {
  return (await client.get<BotJob>(`/admin/jobs/${id}`)).data;
}

// ---------------------------------------------------------------------------
// Finance — /admin/finance/*
// ---------------------------------------------------------------------------

/** Revenue/activations/payouts totals + a daily series over the last `days` days. */
export async function getFinanceSummary(days = 30): Promise<FinanceSummary> {
  return (await client.get<FinanceSummary>("/admin/finance/summary", { params: { days } })).data;
}

/** Raw ledger rows, filterable by kind/user/date range. */
export async function getFinanceTransactions(
  query?: FinanceTransactionsQuery
): Promise<CursorPage<FinanceTransactionItem>> {
  return (
    await client.get<CursorPage<FinanceTransactionItem>>("/admin/finance/transactions", { params: query })
  ).data;
}

/** Per-inviter referral counts and paid-out sums. */
export async function getFinanceReferrals(params?: {
  limit?: number;
  cursor?: string;
}): Promise<CursorPage<FinanceReferralItem>> {
  return (
    await client.get<CursorPage<FinanceReferralItem>>("/admin/finance/referrals", { params })
  ).data;
}

// ---------------------------------------------------------------------------
// Analytics — /admin/analytics/overview
// ---------------------------------------------------------------------------

/** Daily-rollup series plus today's live counters. */
export async function getAnalyticsOverview(days = 30): Promise<AnalyticsOverview> {
  return (await client.get<AnalyticsOverview>("/admin/analytics/overview", { params: { days } })).data;
}

// ---------------------------------------------------------------------------
// System, errors, audit — /admin/system, /admin/errors, /admin/audit
// ---------------------------------------------------------------------------

/** DB size/WAL, table counts, scheduler heartbeats, Redis availability, build version, uptime. */
export async function getSystemInfo(): Promise<SystemInfo> {
  return (await client.get<SystemInfo>("/admin/system")).data;
}

/** Recent `error_log` rows, newest first. */
export async function getErrorLog(query?: ErrorLogQuery): Promise<CursorPage<ErrorLogItem>> {
  return (await client.get<CursorPage<ErrorLogItem>>("/admin/errors", { params: query })).data;
}

/** Recent `admin_audit_log` rows, optionally filtered by actor/action. */
export async function getAuditLog(query?: AuditLogQuery): Promise<CursorPage<AuditLogItem>> {
  return (await client.get<CursorPage<AuditLogItem>>("/admin/audit", { params: query })).data;
}
