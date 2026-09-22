/* eslint-disable react-refresh/only-export-components -- the kit ships helpers next to their component. */
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { useT } from "../../../i18n/useT";
import { roleAtLeast, type AdminRole } from "../hooks/useAdminRole";
import { ADMIN_PAGES } from "../registry";

const STORAGE_KEY = "vakant-admin-rail-pinned";

export function readRailPinned(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export type RailProps = {
  role: AdminRole | null;
  pinned: boolean;
  onPinnedChange: (pinned: boolean) => void;
};

/**
 * Desktop navigation (≥1024px): a 56px icon rail that expands to 220px on
 * hover and can be pinned open with ⌘/Ctrl+B (spec §1.7).
 */
export default function Rail({ role, pinned, onPinnedChange }: RailProps) {
  const t = useT();
  const [hovered, setHovered] = useState(false);
  const expanded = pinned || hovered;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "b" || !(event.ctrlKey || event.metaKey)) return;
      event.preventDefault();
      const next = !pinned;
      onPinnedChange(next);
      try {
        localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      } catch {
        // Blocked storage: the pin is a convenience only.
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [pinned, onPinnedChange]);

  const pages = ADMIN_PAGES.filter(
    (page) => !page.hidden && roleAtLeast(role, page.minRole),
  );

  return (
    <nav
      aria-label={t("admin.nav.aria")}
      title={t(pinned ? "admin.rail.unpin" : "admin.rail.pin")}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="fixed inset-y-0 left-0 z-40 hidden shrink-0 flex-col gap-0.5 overflow-y-auto overflow-x-hidden border-r border-border bg-surface py-2 transition-[width] duration-150 lg:flex"
      style={{ width: expanded ? 220 : 56 }}
    >
      {pages.map((page) => (
        <NavLink
          key={page.id}
          to={page.path ? `/admin/${page.path}` : "/admin"}
          end={!page.path}
          title={t(page.labelKey)}
          className={({ isActive }) =>
            `mx-1.5 flex h-9 items-center gap-2.5 rounded-xl px-[14px] text-[13px] font-medium transition-colors ${
              isActive
                ? "bg-primary/10 font-semibold text-primary"
                : "text-muted hover:bg-surfaceAlt hover:text-text"
            }`
          }
        >
          <page.icon size={16} aria-hidden="true" className="shrink-0" />
          <span className={`truncate ${expanded ? "" : "sr-only"}`}>{t(page.labelKey)}</span>
        </NavLink>
      ))}
    </nav>
  );
}
