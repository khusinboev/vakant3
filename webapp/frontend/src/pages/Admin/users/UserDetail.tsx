import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { adminKeys, getAdminUser } from "../../../api/admin";
import type { AdminUserDetail, AdminUserListItem } from "../../../api/adminTypes";
import type { TranslationKey } from "../../../i18n";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import ErrorCard from "../components/ErrorCard";
import UserActions from "./UserActions";
import UserStatusBadges from "./UserBadges";
import UserSaves from "./UserSaves";
import { displayName, langLabelKey, signedAmount } from "./format";

export type UserDetailProps = {
  /** The row that was clicked — shown while the full profile loads. */
  fallbackUser: AdminUserListItem;
};

function Section({ titleKey, children }: { titleKey: TranslationKey; children: ReactNode }) {
  const t = useT();
  return (
    <section className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted">{t(titleKey)}</h3>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1.5 last:border-b-0">
      <dt className="shrink-0 text-xs text-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-xs font-medium text-text">{children}</dd>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface px-3 py-2">
      <p className="text-[11px] text-muted">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-text">{value}</p>
    </div>
  );
}

/**
 * The drawer body: profile, wallet, counts, recent ledger/events, notification
 * settings, referrer, the (lazy) saves list and the action panel.
 *
 * The list row is used as the immediate fallback so the drawer never opens
 * empty; the detail query then fills in everything the list does not carry.
 */
export default function UserDetail({ fallbackUser }: UserDetailProps) {
  const t = useT();
  const { formatMoney, formatNumber, formatDate, formatDateTime } = useLocale();
  const userId = fallbackUser.user_id;

  const detail = useQuery<AdminUserDetail>({
    queryKey: adminKeys.userDetail(userId),
    queryFn: () => getAdminUser(userId),
    retry: false,
    staleTime: 15_000,
  });

  const user = detail.data?.user ?? fallbackUser;
  const counts = detail.data?.counts;
  const wallet = detail.data?.wallet;
  const langKey = langLabelKey(user.lang);

  return (
    <div className="space-y-5 pb-4" aria-busy={detail.isLoading}>
      <div className="space-y-2">
        <UserStatusBadges user={user} withProTerm />
        {user.banned && user.banned_reason && (
          <p className="rounded-xl bg-danger/10 px-3 py-2 text-xs text-danger">
            {t("adminUsers.detail.banReason")}: {user.banned_reason}
          </p>
        )}
      </div>

      <UserActions user={user} />

      {detail.isError && <ErrorCard error={detail.error} onRetry={() => void detail.refetch()} />}

      <Section titleKey="adminUsers.detail.profile">
        <dl className="rounded-xl border border-border bg-surfaceAlt px-3 py-1">
          <Row label="ID">{user.user_id}</Row>
          <Row label={t("adminUsers.detail.username")}>
            {user.username ? `@${user.username}` : "—"}
          </Row>
          <Row label={t("adminUsers.detail.lang")}>{langKey ? t(langKey) : (user.lang ?? "—")}</Row>
          <Row label={t("adminUsers.detail.region")}>{user.region ?? "—"}</Row>
          <Row label={t("adminUsers.detail.district")}>{user.district ?? "—"}</Row>
          <Row label={t("adminUsers.detail.joined")}>
            {user.date ? formatDateTime(user.date) : "—"}
          </Row>
          <Row label={t("adminUsers.detail.lastSeen")}>
            {user.last_seen_at ? formatDateTime(user.last_seen_at) : "—"}
          </Row>
        </dl>
      </Section>

      <Section titleKey="adminUsers.detail.wallet">
        <dl className="rounded-xl border border-border bg-surfaceAlt px-3 py-1">
          <Row label={t("adminUsers.detail.balance")}>
            {formatMoney(wallet?.balance ?? user.balance)}
          </Row>
          <Row label={t("adminUsers.detail.proUntil")}>
            {wallet?.is_pro ?? user.is_pro
              ? ((wallet?.pro_until ?? user.pro_until)
                  ? formatDate((wallet?.pro_until ?? user.pro_until) as number)
                  : t("adminUsers.badge.unlimited"))
              : "—"}
          </Row>
        </dl>
      </Section>

      {counts && (
        <Section titleKey="adminUsers.detail.counts">
          <div className="grid grid-cols-2 gap-2">
            <Stat label={t("adminUsers.counts.saves")} value={formatNumber(counts.saves)} />
            <Stat label={t("adminUsers.counts.referrals")} value={formatNumber(counts.referrals)} />
            <Stat label={t("adminUsers.counts.payouts")} value={formatMoney(counts.payouts_sum)} />
            <Stat
              label={t("adminUsers.counts.resumeExports")}
              value={formatNumber(counts.resume_exports)}
            />
          </div>
        </Section>
      )}

      <Section titleKey="adminUsers.detail.referrer">
        {detail.data?.referrer ? (
          <p className="rounded-xl border border-border bg-surfaceAlt px-3 py-2 text-xs text-text">
            {displayName(detail.data.referrer)} · {detail.data.referrer.user_id}
          </p>
        ) : (
          <p className="text-xs text-muted">{t("adminUsers.empty.referrer")}</p>
        )}
      </Section>

      <Section titleKey="adminUsers.detail.notifications">
        <p className="text-xs text-text">
          {detail.data?.notification_settings
            ? t(
                detail.data.notification_settings.enabled
                  ? "adminUsers.notif.enabled"
                  : "adminUsers.notif.disabled",
              )
            : t("adminUsers.notif.none")}
        </p>
      </Section>

      <Section titleKey="adminUsers.detail.transactions">
        {detail.data && detail.data.recent_transactions.length > 0 ? (
          <ul className="space-y-1">
            {detail.data.recent_transactions.map((tx) => (
              <li
                key={tx.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-border bg-surfaceAlt px-3 py-2"
              >
                <span className="min-w-0">
                  <span className="block truncate text-xs font-medium text-text">{tx.kind}</span>
                  <span className="block truncate text-[11px] text-muted">
                    {formatDateTime(tx.created_at)}
                    {tx.actor_id ? ` · ${t("adminUsers.tx.actor", { id: tx.actor_id })}` : ""}
                  </span>
                </span>
                <span
                  className={`shrink-0 text-xs font-semibold ${tx.amount < 0 ? "text-danger" : "text-success"}`}
                >
                  {signedAmount(tx.amount, formatMoney(tx.amount))}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted">{t("adminUsers.empty.transactions")}</p>
        )}
      </Section>

      <Section titleKey="adminUsers.detail.events">
        {detail.data && detail.data.recent_events.length > 0 ? (
          <ul className="space-y-1">
            {detail.data.recent_events.map((event) => (
              <li
                key={event.id}
                className="flex items-baseline justify-between gap-3 rounded-lg border border-border bg-surfaceAlt px-2.5 py-1.5"
              >
                <span className="min-w-0 truncate font-mono text-[11px] text-text">
                  {event.event_name}
                  {event.step ? ` · ${event.step}` : ""}
                </span>
                <span className="shrink-0 text-[11px] text-muted">
                  {formatDate(event.created_at)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted">{t("adminUsers.empty.events")}</p>
        )}
      </Section>

      <Section titleKey="adminUsers.detail.saves">
        <UserSaves userId={userId} />
      </Section>
    </div>
  );
}
