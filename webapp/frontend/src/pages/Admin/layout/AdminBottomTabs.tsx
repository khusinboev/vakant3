import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import BottomSheet from "../../../components/ui/BottomSheet";
import { useKeyboardOpen } from "../../../hooks/useKeyboardOpen";
import { useT } from "../../../i18n/useT";
import { roleAtLeast, type AdminRole } from "../hooks/useAdminRole";
import { ADMIN_GROUPS, ADMIN_PAGES, MOBILE_PRIMARY_PAGES, type AdminPageId } from "../registry";
import { adminPagePath } from "../routing";

export type AdminBottomTabsProps = {
  active: AdminPageId;
  role: AdminRole | null;
};

/**
 * Phone navigation: four primary sections plus a "More" sheet with everything
 * the actor's role allows.
 *
 * It sits directly above the app's own `BottomNav` (which `Layout` renders for
 * every route), hence the `bottom` offset; `AdminLayout` reserves the matching
 * padding. Like `BottomNav` it disappears while the soft keyboard is up — and
 * `useKeyboardOpen` must therefore be called before any early return.
 */
export default function AdminBottomTabs({ active, role }: AdminBottomTabsProps) {
  const t = useT();
  const navigate = useNavigate();
  const keyboardOpen = useKeyboardOpen();
  const [sheetOpen, setSheetOpen] = useState(false);

  const allowed = ADMIN_PAGES.filter((page) => roleAtLeast(role, page.minRole));
  const primary = MOBILE_PRIMARY_PAGES.map((id) => allowed.find((page) => page.id === id)).filter(
    (page): page is (typeof allowed)[number] => Boolean(page),
  );
  const activeInPrimary = primary.some((page) => page.id === active);

  if (keyboardOpen) return null;

  return (
    <>
      <nav
        aria-label={t("admin.nav.aria")}
        className="fixed inset-x-0 z-30 border-t border-border bg-surface/95 backdrop-blur lg:hidden"
        style={{ bottom: "calc(3.375rem + var(--bottom-safe, 0px))" }}
      >
        <ul
          className="mx-auto grid max-w-2xl px-[var(--tg-content-safe-area-left)] pr-[var(--tg-content-safe-area-right)]"
          style={{ gridTemplateColumns: `repeat(${primary.length + 1}, minmax(0, 1fr))` }}
        >
          {primary.map((page) => {
            const isActive = page.id === active;
            return (
              <li key={page.id}>
                <Link
                  to={adminPagePath(page.id)}
                  aria-current={isActive ? "page" : undefined}
                  className={`flex flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-semibold ${
                    isActive ? "text-primary" : "text-muted"
                  }`}
                >
                  <page.icon size={16} aria-hidden="true" />
                  <span className="max-w-full truncate px-0.5">{t(page.labelKey)}</span>
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setSheetOpen(true)}
              aria-haspopup="dialog"
              aria-expanded={sheetOpen}
              className={`flex w-full flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-semibold ${
                !activeInPrimary ? "text-primary" : "text-muted"
              }`}
            >
              <MoreHorizontal size={16} aria-hidden="true" />
              <span>{t("admin.nav.more")}</span>
            </button>
          </li>
        </ul>
      </nav>

      <BottomSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        title={t("admin.nav.allPages")}
      >
        <div className="space-y-4">
          {ADMIN_GROUPS.map((group) => {
            const pages = allowed.filter((page) => page.group === group.id);
            if (pages.length === 0) return null;
            return (
              <div key={group.id}>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-muted">
                  {t(group.labelKey)}
                </p>
                <ul className="grid grid-cols-2 gap-2">
                  {pages.map((page) => (
                    <li key={page.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setSheetOpen(false);
                          navigate(adminPagePath(page.id));
                        }}
                        aria-current={page.id === active ? "page" : undefined}
                        className={`tap-target flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-sm ${
                          page.id === active
                            ? "border-primary bg-primary/10 font-semibold text-primary"
                            : "border-border bg-surface text-text"
                        }`}
                      >
                        <page.icon size={15} aria-hidden="true" />
                        <span className="min-w-0 truncate">{t(page.labelKey)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </BottomSheet>
    </>
  );
}
