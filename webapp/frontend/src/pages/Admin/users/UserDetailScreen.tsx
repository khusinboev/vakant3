import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Ban, BadgeCheck, Eraser, MessageSquare, Wallet } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { adminKeys, getAdminUser } from "../../../api/admin";
import type { AdminUserDetail } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";
import ErrorCard from "../components/ErrorCard";
import { useAdminRole } from "../hooks/useAdminRole";
import {
  Accordion,
  KeyValue,
  List,
  ListRow,
  Skeleton,
  StatusChip,
  useAdminHeader,
  type AccordionItem,
} from "../ui";
import UserActionSheet from "./UserActionSheet";
import UserResumeSection from "./UserResumeSection";
import UserSaves from "./UserSaves";
import {
  displayName,
  isUserAction,
  langLabelKey,
  signedAmount,
  userActionPath,
  usernameLine,
} from "./format";

/**
 * `/admin/users/:id` — a full screen on a phone, the same component beside the
 * list on a desktop. The five actions are sub-routes
 * (`/admin/users/:id/action/:action`), so each one is a history entry that the
 * Telegram BackButton closes (spec §2).
 */
export default function UserDetailScreen() {
  const params = useParams();
  const t = useT();
  const navigate = useNavigate();
  const { formatMoney, formatNumber, formatDate, formatDateTime } = useLocale();
  const { atLeast } = useAdminRole();

  const userId = Number(params.id);
  const action = params.action;

  const detail = useQuery<AdminUserDetail>({
    queryKey: adminKeys.userDetail(userId),
    queryFn: () => getAdminUser(userId),
    retry: false,
    staleTime: 15_000,
    enabled: Number.isSafeInteger(userId) && userId > 0,
  });

  const user = detail.data?.user;
  const title = user ? displayName(user) : `#${params.id ?? ""}`;
  const open = (key: string) => navigate(userActionPath(userId, key));

  useAdminHeader({
    title,
    menu: [
      {
        labelKey: "adminUsers.action.pro",
        icon: BadgeCheck,
        onClick: () => open("pro"),
        hidden: !atLeast("admin"),
      },
      {
        labelKey: "adminUsers.action.balance",
        icon: Wallet,
        onClick: () => open("balance"),
        hidden: !atLeast("admin"),
      },
      {
        labelKey: user?.banned ? "adminUsers.action.unban" : "adminUsers.action.ban",
        icon: Ban,
        danger: !user?.banned,
        onClick: () => open("ban"),
        hidden: !atLeast("moderator"),
      },
      {
        labelKey: "adminUsers.action.message",
        icon: MessageSquare,
        onClick: () => open("message"),
        hidden: !atLeast("moderator"),
      },
      {
        labelKey: "adminUsers.action.reset",
        icon: Eraser,
        danger: true,
        onClick: () => open("reset"),
        hidden: !atLeast("admin"),
      },
    ],
  });

  const data = detail.data;

  const sections = useMemo<AccordionItem[]>(() => {
    if (!data || !user) return [];
    const wallet = data.wallet;
    const counts = data.counts;
    const notifications = data.notification_settings;

    return [
      {
        id: "wallet",
        titleKey: "adminUsers.detail.wallet",
        summary: formatMoney(wallet?.balance ?? user.balance),
        content: (
          <div className="space-y-2">
            <KeyValue
              card={false}
              rows={[
                {
                  labelKey: "adminUsers.detail.balance",
                  value: formatMoney(wallet?.balance ?? user.balance),
                },
                {
                  labelKey: "adminUsers.detail.proUntil",
                  value: (wallet?.is_pro ?? user.is_pro)
                    ? ((wallet?.pro_until ?? user.pro_until)
                        ? formatDate((wallet?.pro_until ?? user.pro_until) as number)
                        : t("adminUsers.badge.unlimited"))
                    : "—",
                },
              ]}
            />
            {data.recent_transactions.length > 0 ? (
              <List card={false} ariaLabelKey="adminUsers.detail.transactions">
                {data.recent_transactions.map((tx) => (
                  <ListRow
                    key={tx.id}
                    title={tx.kind}
                    subtitle={`${formatDateTime(tx.created_at)}${
                      tx.actor_id ? ` · ${t("adminUsers.tx.actor", { id: tx.actor_id })}` : ""
                    }`}
                    trailing={
                      <span
                        className={`text-[13px] font-semibold tabular-nums ${
                          tx.amount < 0 ? "text-danger" : "text-success"
                        }`}
                      >
                        {signedAmount(tx.amount, formatMoney(tx.amount))}
                      </span>
                    }
                  />
                ))}
              </List>
            ) : (
              <p className="text-[11px] text-muted">{t("adminUsers.empty.transactions")}</p>
            )}
          </div>
        ),
      },
      {
        id: "referral",
        titleKey: "adminUsers.detail.referral",
        summary: formatNumber(counts?.referrals ?? 0),
        content: (
          <KeyValue
            card={false}
            rows={[
              { labelKey: "adminUsers.counts.referrals", value: formatNumber(counts?.referrals ?? 0) },
              {
                labelKey: "adminUsers.counts.payouts",
                value: formatMoney(counts?.payouts_sum ?? 0),
              },
              {
                labelKey: "adminUsers.detail.referrer",
                value: data.referrer
                  ? `${displayName(data.referrer)} · ${data.referrer.user_id}`
                  : t("adminUsers.empty.referrer"),
              },
            ]}
          />
        ),
      },
      {
        id: "resume",
        titleKey: "adminUsers.detail.resume",
        summary: formatNumber(counts?.resume_exports ?? 0),
        content: <UserResumeSection userId={user.user_id} exports={counts?.resume_exports} />,
      },
      {
        id: "notifications",
        titleKey: "adminUsers.detail.notifications",
        summary: t(
          notifications
            ? notifications.enabled
              ? "adminUsers.notif.enabled"
              : "adminUsers.notif.disabled"
            : "adminUsers.notif.none",
        ),
        content: (
          <KeyValue
            card={false}
            rows={[
              {
                labelKey: "adminUsers.detail.notifications",
                value: t(
                  notifications
                    ? notifications.enabled
                      ? "adminUsers.notif.enabled"
                      : "adminUsers.notif.disabled"
                    : "adminUsers.notif.none",
                ),
                tone: notifications?.enabled ? "success" : "neutral",
              },
              {
                labelKey: "adminUsers.detail.lastSeen",
                value: notifications ? formatDateTime(notifications.updated_at) : "—",
                hidden: !notifications,
              },
            ]}
          />
        ),
      },
      {
        id: "saves",
        titleKey: "adminUsers.detail.saves",
        summary: formatNumber(counts?.saves ?? 0),
        content: <UserSaves userId={user.user_id} />,
      },
    ];
  }, [data, user, formatMoney, formatNumber, formatDate, formatDateTime, t]);

  if (detail.isError) {
    return <ErrorCard error={detail.error} onRetry={() => void detail.refetch()} />;
  }

  if (!user) return <Skeleton rows={6} />;

  const langKey = langLabelKey(user.lang);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusChip
          status={user.is_pro ? "pro" : "free"}
          labelKey={user.is_pro ? "adminUsers.badge.pro" : "adminUsers.badge.free"}
        />
        {user.is_pro && (
          <span className="text-[11px] text-muted">
            {user.pro_until
              ? t("adminUsers.badge.until", { date: formatDate(user.pro_until) })
              : t("adminUsers.badge.unlimited")}
          </span>
        )}
        {user.banned && <StatusChip status="banned" labelKey="adminUsers.badge.banned" />}
        {user.blocked && <StatusChip status="blocked" labelKey="adminUsers.badge.blocked" />}
      </div>

      {user.banned && user.banned_reason && (
        <p className="rounded-xl bg-danger/10 px-3 py-2 text-[11px] text-danger">
          {t("adminUsers.detail.banReason")}: {user.banned_reason}
        </p>
      )}

      <KeyValue
        rows={[
          { label: "ID", value: usernameLine(user) },
          {
            labelKey: "adminUsers.detail.lang",
            value: langKey ? t(langKey) : (user.lang ?? "—"),
          },
          { labelKey: "adminUsers.detail.region", value: user.region ?? "—" },
          { labelKey: "adminUsers.detail.district", value: user.district ?? "—" },
          { labelKey: "adminUsers.detail.joined", value: user.date ? formatDateTime(user.date) : "—" },
          {
            labelKey: "adminUsers.detail.lastSeen",
            value: user.last_seen_at ? formatDateTime(user.last_seen_at) : "—",
          },
          { labelKey: "adminUsers.detail.balance", value: formatMoney(user.balance) },
        ]}
      />

      <Accordion queryKey="section" items={sections} />

      {isUserAction(action) && <UserActionSheet user={user} action={action} />}
    </div>
  );
}
