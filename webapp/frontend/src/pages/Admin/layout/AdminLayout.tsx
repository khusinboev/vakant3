import type { ReactNode } from "react";

import { useT } from "../../../i18n/useT";
import ConfirmDialogHost from "../components/ConfirmDialogHost";
import { useIsDesktop } from "../hooks/useMediaQuery";
import type { AdminRole } from "../hooks/useAdminRole";
import type { AdminPageId } from "../registry";
import AdminBottomTabs from "./AdminBottomTabs";
import AdminHeader from "./AdminHeader";
import AdminSidebar from "./AdminSidebar";

export type AdminLayoutProps = {
  /** Already translated title of the active page. */
  title: string;
  role: AdminRole | null;
  active: AdminPageId;
  children: ReactNode;
};

/**
 * The admin shell: a grouped sidebar from ≥1024px, bottom tabs below it, and
 * one header carrying the page title, the actor's role and the language/theme
 * quick switches.
 *
 * It breaks out of `Layout`'s padding with negative margins (the panel is
 * rendered inside the app `Layout`, which also supplies the app-wide
 * `BottomNav` at the very bottom).
 */
export default function AdminLayout({ title, role, active, children }: AdminLayoutProps) {
  const t = useT();
  const isDesktop = useIsDesktop();

  return (
    <div className="-mx-4 -my-4 min-h-[calc(var(--app-viewport-height)-3.5rem)] bg-bg">
      <div className="lg:grid lg:grid-cols-[14rem_minmax(0,1fr)]">
        {isDesktop && <AdminSidebar active={active} role={role} />}

        <div className="min-w-0">
          <AdminHeader title={title} role={role} />
          <main
            aria-label={t("admin.title")}
            className="px-4 py-4 pb-[4.5rem] pl-[calc(1rem+var(--tg-content-safe-area-left))] pr-[calc(1rem+var(--tg-content-safe-area-right))] lg:pb-8"
          >
            {children}
          </main>
        </div>
      </div>

      {!isDesktop && <AdminBottomTabs active={active} role={role} />}
      <ConfirmDialogHost />
    </div>
  );
}
