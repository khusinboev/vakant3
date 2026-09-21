import { Grid2x2, Home, ShieldCheck, UserCircle2 } from "lucide-react";
import { NavLink } from "react-router-dom";

import { useKeyboardOpen } from "../../hooks/useKeyboardOpen";
import { useT } from "../../i18n/useT";
import type { TranslationKey } from "../../i18n";
import { useAdminRole } from "../../pages/Admin/hooks/useAdminRole";

const links: Array<{ to: string; labelKey: TranslationKey; icon: typeof Home }> = [
  { to: "/app", labelKey: "nav.home", icon: Home },
  { to: "/profile", labelKey: "nav.profile", icon: UserCircle2 },
  { to: "/hub", labelKey: "nav.hub", icon: Grid2x2 },
];

/**
 * `fixed` is accepted for backwards compatibility (ResumeStudio passes it) —
 * the nav is always rendered fixed to the viewport bottom.
 */
export default function BottomNav({ fixed = true }: { fixed?: boolean }) {
  const keyboardOpen = useKeyboardOpen();
  const t = useT();

  // The role comes from the shared `["auth","gate"]` query (one request for the
  // whole app, with a `/admin/state` fallback while `/auth/gate` is rolling out).
  const { role } = useAdminRole();

  // Hide while the soft keyboard is up so the nav never floats above it.
  if (keyboardOpen) return null;

  const navLinks = role
    ? [...links, { to: "/admin", labelKey: "nav.admin" as TranslationKey, icon: ShieldCheck }]
    : links;

  const navCls = fixed
    ? "fixed bottom-0 left-0 right-0 z-20 border-t border-border bg-surface/95 backdrop-blur"
    : "border-t border-border bg-surface/95 backdrop-blur shrink-0";

  return (
    <nav className={navCls} style={{ paddingBottom: "var(--bottom-safe, 0px)" }}>
      <ul
        className="mx-auto grid max-w-2xl px-[var(--tg-content-safe-area-left)] pr-[var(--tg-content-safe-area-right)]"
        style={{ gridTemplateColumns: `repeat(${navLinks.length}, minmax(0, 1fr))` }}
      >
        {navLinks.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                `tap-target flex flex-col items-center justify-center gap-1 py-2 text-xs ${isActive ? "text-primary" : "text-muted"}`
              }
            >
              <item.icon size={18} />
              <span>{t(item.labelKey)}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
