import { Megaphone, Radio, Send } from "lucide-react";
import { Link } from "react-router-dom";

import { useT } from "../../../i18n/useT";
import { useAdminHeader } from "../hooks/useAdminHeader";
import { roleAtLeast, useAdminRole } from "../hooks/useAdminRole";
import { ADMIN_GROUPS, ADMIN_PAGES } from "../registry";
import { adminPagePath } from "../routing";

const QUICK = [
  { to: "/admin/autopost", labelKey: "admin.more.quick.postNow", icon: Send, minRole: "admin" },
  {
    to: "/admin/broadcasts/new",
    labelKey: "admin.more.quick.newBroadcast",
    icon: Megaphone,
    minRole: "admin",
  },
  { to: "/admin/channels", labelKey: "admin.more.quick.addChannel", icon: Radio, minRole: "admin" },
] as const;

/**
 * "Ko'proq" — every section the actor's role allows, as a 3-column grid, plus
 * the quick actions. It is a page, not a sheet, so back leaves it naturally.
 */
export default function MorePage() {
  const t = useT();
  const { role } = useAdminRole();
  useAdminHeader({ titleKey: "admin.more.title" });

  const quick = QUICK.filter((action) => roleAtLeast(role, action.minRole));

  return (
    <div className="space-y-3">
      {quick.length > 0 && (
        <section>
          <h2 className="mb-1.5 text-[11px] font-bold uppercase tracking-wider text-muted">
            {t("admin.more.quickActions")}
          </h2>
          <div className="flex flex-wrap gap-1.5">
            {quick.map((action) => (
              <Link
                key={action.to}
                to={action.to}
                className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-border bg-surface px-3 text-[12px] font-semibold text-text hover:bg-surfaceAlt"
              >
                <action.icon size={14} aria-hidden="true" />
                {t(action.labelKey)}
              </Link>
            ))}
          </div>
        </section>
      )}

      {ADMIN_GROUPS.map((group) => {
        const pages = ADMIN_PAGES.filter(
          (page) => page.group === group.id && !page.hidden && roleAtLeast(role, page.minRole),
        );
        if (pages.length === 0) return null;

        return (
          <section key={group.id}>
            <h2 className="mb-1.5 text-[11px] font-bold uppercase tracking-wider text-muted">
              {t(group.labelKey)}
            </h2>
            <ul className="grid grid-cols-3 gap-1.5">
              {pages.map((page) => (
                <li key={page.id}>
                  <Link
                    to={adminPagePath(page.id)}
                    className="flex min-h-[64px] flex-col items-center justify-center gap-1 rounded-xl border border-border bg-surface px-1.5 py-2 text-center text-[11px] font-semibold text-text hover:bg-surfaceAlt"
                  >
                    <page.icon size={16} aria-hidden="true" className="text-primary" />
                    <span className="line-clamp-2 leading-tight">{t(page.labelKey)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
