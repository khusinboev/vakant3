import { Home, Megaphone, MoreHorizontal, Users } from "lucide-react";
import { NavLink } from "react-router-dom";
import type { ElementType } from "react";

import type { TranslationKey } from "../../../i18n";
import { useT } from "../../../i18n/useT";
import { roleAtLeast, type AdminRole } from "../hooks/useAdminRole";
import { Badge } from "../ui/Chip";

type BarItem = {
  id: string;
  to: string;
  labelKey: TranslationKey;
  icon: ElementType;
  minRole: AdminRole;
  /** Matches deeper routes too (`/admin/users/42`). */
  end?: boolean;
  badge?: number;
};

export type AdminBarProps = {
  role: AdminRole | null;
  /** e.g. the number of running broadcasts. */
  broadcastBadge?: number;
};

/**
 * The panel's only bottom bar: 44px, four targets, never hidden by the soft
 * keyboard (spec §1.2) — the app's own BottomNav is not rendered under
 * `/admin`, so this is the single one.
 */
export default function AdminBar({ role, broadcastBadge }: AdminBarProps) {
  const t = useT();

  const items: BarItem[] = ([
    { id: "home", to: "/admin", labelKey: "admin.bar.home", icon: Home, minRole: "viewer", end: true },
    { id: "users", to: "/admin/users", labelKey: "admin.bar.users", icon: Users, minRole: "moderator" },
    {
      id: "broadcasts",
      to: "/admin/broadcasts",
      labelKey: "admin.bar.broadcasts",
      icon: Megaphone,
      minRole: "admin",
      badge: broadcastBadge,
    },
    { id: "more", to: "/admin/more", labelKey: "admin.bar.more", icon: MoreHorizontal, minRole: "viewer" },
  ] as BarItem[]).filter((item) => roleAtLeast(role, item.minRole));

  return (
    <nav
      aria-label={t("admin.nav.aria")}
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 backdrop-blur lg:hidden"
      style={{ paddingBottom: "var(--bottom-safe, 0px)" }}
    >
      <ul
        className="mx-auto grid max-w-2xl pl-[var(--tg-content-safe-area-left)] pr-[var(--tg-content-safe-area-right)]"
        style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
      >
        {items.map((item) => (
          <li key={item.id}>
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex h-[44px] flex-col items-center justify-center gap-0.5 text-[11px] font-semibold ${
                  isActive ? "text-primary" : "text-muted"
                }`
              }
            >
              <span className="relative inline-flex">
                <item.icon size={16} aria-hidden="true" />
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute -right-2 -top-1">
                    <Badge count={item.badge} tone="danger" />
                  </span>
                )}
              </span>
              <span className="max-w-full truncate px-0.5">{t(item.labelKey)}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
