import { useCallback, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";

import { useT } from "../../../i18n/useT";
import { roleAtLeast, type AdminRole } from "../hooks/useAdminRole";
import { ADMIN_GROUPS, ADMIN_PAGES, type AdminGroupId, type AdminPageId } from "../registry";
import { adminPagePath } from "../routing";

const STORAGE_KEY = "vakant-admin-nav-groups";

function readCollapsed(): AdminGroupId[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AdminGroupId[]) : [];
  } catch {
    return [];
  }
}

export type AdminSidebarProps = {
  active: AdminPageId;
  role: AdminRole | null;
};

/** Desktop (≥1024px) navigation: grouped, collapsible, role-filtered. */
export default function AdminSidebar({ active, role }: AdminSidebarProps) {
  const t = useT();
  const [collapsed, setCollapsed] = useState<AdminGroupId[]>(readCollapsed);

  const toggle = useCallback((group: AdminGroupId) => {
    setCollapsed((current) => {
      const next = current.includes(group)
        ? current.filter((id) => id !== group)
        : [...current, group];
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Private mode / blocked storage: the preference is a convenience only.
      }
      return next;
    });
  }, []);

  return (
    <nav
      aria-label={t("admin.nav.aria")}
      className="sticky top-14 h-[calc(var(--app-viewport-height)-3.5rem)] shrink-0 overflow-y-auto border-r border-border bg-surface px-2 py-3"
    >
      {ADMIN_GROUPS.map((group) => {
        const pages = ADMIN_PAGES.filter(
          (page) => page.group === group.id && roleAtLeast(role, page.minRole),
        );
        if (pages.length === 0) return null;
        const isOpen = !collapsed.includes(group.id);

        return (
          <div key={group.id} className="mb-1">
            <button
              type="button"
              onClick={() => toggle(group.id)}
              aria-expanded={isOpen}
              className="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-muted hover:bg-surfaceAlt"
            >
              {t(group.labelKey)}
              <ChevronDown
                size={12}
                aria-hidden="true"
                className={`transition-transform ${isOpen ? "" : "-rotate-90"}`}
              />
            </button>

            {isOpen && (
              <ul className="mt-0.5 space-y-0.5">
                {pages.map((page) => {
                  const isActive = page.id === active;
                  return (
                    <li key={page.id}>
                      <Link
                        to={adminPagePath(page.id)}
                        aria-current={isActive ? "page" : undefined}
                        className={`flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm font-medium transition-colors ${
                          isActive
                            ? "bg-primary/10 font-semibold text-primary"
                            : "text-muted hover:bg-surfaceAlt hover:text-text"
                        }`}
                      >
                        <page.icon size={15} aria-hidden="true" />
                        <span className="truncate">{t(page.labelKey)}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </nav>
  );
}
