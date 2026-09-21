import type { ReactNode } from "react";

import type { AdminUserListItem } from "../../../api/adminTypes";
import { useLocale } from "../../../i18n/useLocale";
import { useT } from "../../../i18n/useT";

const TONE = {
  pro: "bg-primary/10 text-primary",
  free: "bg-surfaceAlt text-muted",
  danger: "bg-danger/10 text-danger",
  warning: "bg-warning/10 text-warning",
} as const;

export function Badge({ tone, children }: { tone: keyof typeof TONE; children: ReactNode }) {
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export type UserStatusBadgesProps = {
  user: Pick<AdminUserListItem, "is_pro" | "pro_until" | "banned" | "blocked">;
  /** Adds the Pro expiry next to the Pro badge (detail view). */
  withProTerm?: boolean;
};

/** Pro / banned / blocked, the three states a row must show at a glance. */
export default function UserStatusBadges({ user, withProTerm = false }: UserStatusBadgesProps) {
  const t = useT();
  const { formatDate } = useLocale();

  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {user.is_pro ? (
        <Badge tone="pro">
          {t("adminUsers.badge.pro")}
          {withProTerm && (
            <span className="ml-1 font-normal">
              {user.pro_until
                ? t("adminUsers.badge.until", { date: formatDate(user.pro_until) })
                : t("adminUsers.badge.unlimited")}
            </span>
          )}
        </Badge>
      ) : (
        <Badge tone="free">{t("adminUsers.badge.free")}</Badge>
      )}
      {user.banned && <Badge tone="danger">{t("adminUsers.badge.banned")}</Badge>}
      {user.blocked && <Badge tone="warning">{t("adminUsers.badge.blocked")}</Badge>}
    </span>
  );
}
